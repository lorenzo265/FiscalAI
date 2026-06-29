"""Service do billing — assinatura + sync do webhook Stripe (Marco 2).

Máquina de estados da assinatura:
    trial → ativa → (inadimplente → ativa | cancelada)
    trial → cancelada ; ativa → cancelada
``cancelada`` é TERMINAL — nenhum evento revive (guard anti-revival no webhook).

Webhook é idempotente por ``stripe_event_id`` (UNIQUE em ``evento_billing``).
A assinatura do webhook é validada pelo provider ANTES de qualquer escrita.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.modules.auth.repo import UsuarioRepo
from app.modules.billing.planos import PLANOS_VERSAO, TRIAL_DIAS, plano_para
from app.modules.billing.provider import (
    BillingProvider,
    EventoStripe,
    build_billing_provider,
)
from app.modules.billing.repo import AssinaturaRepo, EventoBillingRepo, FaturaRepo
from app.shared.db.models import Assinatura, EventoBilling, Fatura
from app.shared.exceptions import AssinaturaNaoEncontrada
from app.shared.integrations.email.templates import renderizar_fatura
from app.workers.tasks.email_enviar import enfileirar_email

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_TERMINAL = ("cancelada",)


def _str_ou_none(v: object) -> str | None:
    if v is None or v == "":
        return None
    return str(v)


def _epoch_para_dt(v: object) -> datetime | None:
    if isinstance(v, int | float) and not isinstance(v, bool):
        return datetime.fromtimestamp(float(v), tz=_TZ_BR)
    return None


def _cents_para_decimal(v: object) -> Decimal:
    if isinstance(v, int) and not isinstance(v, bool):
        return (Decimal(v) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
    return Decimal("0.00")


class BillingService:
    def __init__(
        self, settings: Settings, provider: BillingProvider | None = None
    ) -> None:
        self._settings = settings
        self._provider = provider or build_billing_provider(settings)

    # ── API autenticada ──────────────────────────────────────────────────────

    async def iniciar_assinatura(
        self, session: AsyncSession, *, tenant_id: UUID, plano_codigo: str
    ) -> Assinatura:
        """Cria a assinatura em trial + sessão de checkout. Idempotente:
        se já houver assinatura viva (trial/ativa/inadimplente), devolve-a.
        """
        plano = plano_para(plano_codigo)  # raises PlanoInexistente
        repo = AssinaturaRepo(session)
        existente = await repo.ativa_do_tenant(tenant_id)
        if existente is not None:
            log.info(
                "billing.assinatura.ja_existe",
                tenant_id=str(tenant_id),
                assinatura_id=str(existente.id),
            )
            return existente

        agora = datetime.now(tz=_TZ_BR)
        assinatura = Assinatura(
            tenant_id=tenant_id,
            plano_codigo=plano.codigo,
            status="trial",
            trial_ends_at=agora + timedelta(days=TRIAL_DIAS),
            planos_versao=PLANOS_VERSAO,
        )
        await repo.criar(assinatura)  # flush → id disponível

        checkout = await self._provider.criar_checkout(
            assinatura_id=assinatura.id,
            plano=plano,
            stripe_customer_id=None,
        )
        assinatura.checkout_url = checkout.checkout_url
        assinatura.stripe_customer_id = checkout.stripe_customer_id
        await session.commit()
        await session.refresh(assinatura)
        log.info(
            "billing.assinatura.iniciada",
            tenant_id=str(tenant_id),
            assinatura_id=str(assinatura.id),
            plano=plano.codigo,
            provider=checkout.provider,
        )
        return assinatura

    async def cancelar_assinatura(
        self, session: AsyncSession, *, tenant_id: UUID
    ) -> Assinatura:
        repo = AssinaturaRepo(session)
        assinatura = await repo.ativa_do_tenant(tenant_id)
        if assinatura is None:
            raise AssinaturaNaoEncontrada(
                f"Nenhuma assinatura ativa para o tenant {tenant_id}"
            )
        if assinatura.stripe_subscription_id:
            await self._provider.cancelar(
                stripe_subscription_id=assinatura.stripe_subscription_id
            )
        assinatura.status = "cancelada"
        assinatura.atualizado_em = datetime.now(tz=_TZ_BR)
        await session.commit()
        await session.refresh(assinatura)
        log.info("billing.assinatura.cancelada", assinatura_id=str(assinatura.id))
        return assinatura

    # ── Webhook do Stripe ────────────────────────────────────────────────────

    async def processar_webhook(
        self,
        session: AsyncSession,
        *,
        payload: bytes,
        assinatura_header: str | None,
    ) -> None:
        # Valida a assinatura ANTES de tudo (levanta WebhookStripeAssinaturaInvalida).
        evento = self._provider.parse_evento(
            payload=payload, assinatura_header=assinatura_header
        )
        evento_repo = EventoBillingRepo(session)
        if await evento_repo.por_stripe_event(evento.stripe_event_id) is not None:
            log.info(
                "billing.webhook.duplicado_ignorado",
                stripe_event_id=evento.stripe_event_id,
            )
            return

        await self._aplicar_evento(session, evento)
        await evento_repo.criar(
            EventoBilling(
                tenant_id=None,
                stripe_event_id=evento.stripe_event_id,
                tipo=evento.tipo,
                payload=dict(evento.dados),
            )
        )
        await session.commit()
        log.info(
            "billing.webhook.processado",
            stripe_event_id=evento.stripe_event_id,
            tipo=evento.tipo,
        )

    async def _aplicar_evento(
        self, session: AsyncSession, evento: EventoStripe
    ) -> None:
        repo = AssinaturaRepo(session)
        dados = evento.dados

        if evento.tipo == "checkout.session.completed":
            ref = _str_ou_none(dados.get("client_reference_id"))
            if ref is None:
                return
            assinatura = await repo.por_id(UUID(ref))
            if assinatura is None:
                return
            assinatura.stripe_subscription_id = _str_ou_none(dados.get("subscription"))
            cus = _str_ou_none(dados.get("customer"))
            if cus:
                assinatura.stripe_customer_id = cus
            self._transicionar(assinatura, "ativa")

        elif evento.tipo == "invoice.paid":
            assinatura = await self._achar_por_sub(repo, dados)
            if assinatura is None:
                return
            self._transicionar(assinatura, "ativa")
            fim = _epoch_para_dt(dados.get("period_end"))
            if fim is not None:
                assinatura.current_period_end = fim
            await self._registrar_fatura(session, assinatura, dados, status="paga")

        elif evento.tipo == "invoice.payment_failed":
            assinatura = await self._achar_por_sub(repo, dados)
            if assinatura is None:
                return
            self._transicionar(assinatura, "inadimplente")
            await self._registrar_fatura(session, assinatura, dados, status="falhou")

        elif evento.tipo == "customer.subscription.deleted":
            sub_id = _str_ou_none(dados.get("id"))
            if sub_id is None:
                return
            assinatura = await repo.por_stripe_subscription(sub_id)
            if assinatura is None:
                return
            self._transicionar(assinatura, "cancelada")
        # Outros tipos: só persistidos em evento_billing, sem efeito de estado.

    @staticmethod
    async def _achar_por_sub(
        repo: AssinaturaRepo, dados: dict[str, object]
    ) -> Assinatura | None:
        sub_id = _str_ou_none(dados.get("subscription"))
        if sub_id is None:
            return None
        return await repo.por_stripe_subscription(sub_id)

    @staticmethod
    def _transicionar(assinatura: Assinatura, novo: str) -> None:
        """Aplica a transição. ``cancelada`` é terminal: eventos posteriores
        NÃO revivem a assinatura (guard anti-revival; webhook tolerante)."""
        if assinatura.status == novo:
            return
        if assinatura.status in _TERMINAL:
            log.info(
                "billing.transicao.ignorada_terminal",
                assinatura_id=str(assinatura.id),
                de=assinatura.status,
                para=novo,
            )
            return
        assinatura.status = novo
        assinatura.atualizado_em = datetime.now(tz=_TZ_BR)

    @staticmethod
    async def _registrar_fatura(
        session: AsyncSession,
        assinatura: Assinatura,
        dados: dict[str, object],
        *,
        status: str,
    ) -> None:
        invoice_id = _str_ou_none(dados.get("id"))
        if invoice_id is None:
            return
        repo = FaturaRepo(session)
        if await repo.por_stripe_invoice(invoice_id) is not None:
            return  # idempotente — fatura já registrada
        valor = _cents_para_decimal(
            dados.get("amount_paid") or dados.get("amount_due")
        )
        agora = datetime.now(tz=_TZ_BR)
        await repo.criar(
            Fatura(
                tenant_id=assinatura.tenant_id,
                assinatura_id=assinatura.id,
                valor=valor,
                status=status,
                stripe_invoice_id=invoice_id,
                competencia=date(agora.year, agora.month, 1),
                pago_em=agora if status == "paga" else None,
            )
        )

        # Recibo por e-mail quando a fatura é paga (fail-soft — NUNCA quebra o
        # webhook). "falhou" vira inadimplência, tratada à parte. Semântica
        # AT-LEAST-ONCE: o retorno-cedo acima evita re-envio numa re-entrega já
        # COMMITADA, mas o enqueue ocorre antes do commit final (em
        # processar_webhook); se o commit falhar e o Stripe re-entregar, o recibo
        # pode duplicar. Trade-off consciente p/ notificação: não perder > não duplicar.
        if status == "paga":
            try:
                usuario = await UsuarioRepo(session).primeira_do_tenant(
                    assinatura.tenant_id
                )
                if usuario is not None:
                    settings = get_settings()
                    msg = renderizar_fatura(
                        nome=usuario.nome,
                        plano=assinatura.plano_codigo,
                        valor=valor,
                        vencimento=date(agora.year, agora.month, 1),
                        link_pagamento=f"{settings.APP_BASE_URL}/configuracoes",
                    )
                    enfileirar_email(msg, to=usuario.email, tags=["fatura"])
            except Exception:  # notificação nunca bloqueia o billing
                log.warning(
                    "billing.fatura_email_falhou",
                    assinatura_id=str(assinatura.id),
                )
