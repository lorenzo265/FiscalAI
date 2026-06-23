"""Pagamento stub do marketplace (Sprint 13 PR3).

Pipeline:

  1. ``ConsultaPagamentoService.gerar_cobranca(consulta_id)`` — cliente PME
     dispara após consulta atingir ``concluida``. Resolve provider
     (``_FakeProvider`` no MVP), persiste ``cobranca_consulta`` com
     ``idempotency_key = uuid5(NS, "pagto|consulta_id")`` e devolve o link
     de checkout (fake: ``https://fiscalai.local/checkout/<id>``).

  2. Provider chama ``processar_webhook(payload)`` quando paga — marca
     status ``paga``, preenche ``paga_em`` e atualiza
     ``consulta_marketplace.paga_em``. Idempotente: webhook duplicado vira
     no-op.

ADR 0015 documenta a escolha de stub vs Stripe Connect/Pagar.me. Pendência
``docs/pendencias/marketplace-pagamento-real.md`` rastreia o trabalho de
ativação real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.marketplace.repo import ConsultaRepo
from app.shared.db.models import CobrancaConsulta, ConsultaMarketplace
from app.shared.exceptions import (
    CobrancaInvalida,
    CobrancaNaoEncontrada,
    ConsultaNaoEncontrada,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Namespace UUID5 estável para idempotency_key de cobranças. Não mudar.
# uuid5(NAMESPACE_URL, "https://fiscalai.com/marketplace/pagamento")
_NS_PAGAMENTO: UUID = UUID("2c1c0a8e-4d8e-5a9e-9b5b-1c0c6f3a2e5d")


@dataclass(frozen=True, slots=True)
class CobrancaCriada:
    """Saída do provider quando a cobrança é gerada."""

    provider: str
    provider_externo_id: str
    checkout_url: str


class PaymentProvider(Protocol):
    """Contrato mínimo de um provider de pagamento (Stripe/Pagar.me/Pix/etc.)."""

    nome: str

    async def criar_cobranca(
        self,
        *,
        consulta_id: UUID,
        valor: Decimal,
        idempotency_key: UUID,
    ) -> CobrancaCriada:
        """Gera cobrança no provider e devolve identificadores externos."""
        ...


class _FakeProvider:
    """Provider de mentira — gera URL determinística a partir da consulta.

    Em prod vira ``StripeConnectProvider`` ou ``PagarmeProvider``. Mantém a
    mesma interface para que o swap seja injetar outra classe no service.
    """

    nome: str = "fake"

    async def criar_cobranca(
        self,
        *,
        consulta_id: UUID,
        valor: Decimal,
        idempotency_key: UUID,
    ) -> CobrancaCriada:
        return CobrancaCriada(
            provider=self.nome,
            provider_externo_id=f"fake-{idempotency_key.hex[:16]}",
            checkout_url=f"https://fiscalai.local/checkout/{consulta_id}",
        )


def idempotency_pagamento(consulta_id: UUID) -> UUID:
    """uuid5 estável: 1 cobrança por consulta, retry seguro."""
    return uuid5(_NS_PAGAMENTO, f"pagto|{consulta_id}")


class ConsultaPagamentoService:
    """Orquestra geração de cobrança + processamento de webhook."""

    def __init__(self, provider: PaymentProvider | None = None) -> None:
        self._provider: PaymentProvider = provider or _FakeProvider()

    async def gerar_cobranca(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        consulta_id: UUID,
    ) -> CobrancaConsulta:
        consulta = await ConsultaRepo(session).por_id(consulta_id)
        if consulta is None:
            raise ConsultaNaoEncontrada(
                f"Consulta {consulta_id} não encontrada (ou fora do escopo RLS)"
            )
        if consulta.status != "concluida":
            raise CobrancaInvalida(
                f"Consulta em status {consulta.status!r} não pode ser cobrada "
                "(precisa estar 'concluida')"
            )

        idem_key = idempotency_pagamento(consulta_id)
        # FIX #13: gate usa idem_key (uuid5 determinístico, UNIQUE no DB via
        # uq_cobranca_idempotency) em vez de apenas consulta_id. Isso alinha o
        # gate com o contrato do §8.9: a chave de idempotência é o árbitro, não
        # a foreign key de negócio. Ambas as UNIQUEs existem (0033 migration:
        # uq_cobranca_consulta + uq_cobranca_idempotency), mas a idem_key é o
        # ponto de entrada canônico para retry seguro do lado do caller.
        existente = await self._buscar_por_idem_key(session, idem_key)
        if existente is not None:
            return existente

        cobranca_provider = await self._provider.criar_cobranca(
            consulta_id=consulta_id,
            valor=consulta.valor_consulta,
            idempotency_key=idem_key,
        )

        cobranca = CobrancaConsulta(
            tenant_id=tenant_id,
            consulta_id=consulta_id,
            provider=cobranca_provider.provider,
            provider_externo_id=cobranca_provider.provider_externo_id,
            idempotency_key=idem_key,
            valor=consulta.valor_consulta,
            status="pendente",
            checkout_url=cobranca_provider.checkout_url,
        )
        session.add(cobranca)
        try:
            await session.commit()
        except IntegrityError:
            # Race: outra request criou no meio. Refetch via idem_key + devolve.
            await session.rollback()
            existente = await self._buscar_por_idem_key(session, idem_key)
            if existente is None:
                raise
            return existente
        await session.refresh(cobranca)

        log.info(
            "marketplace.cobranca.gerada",
            consulta_id=str(consulta_id),
            cobranca_id=str(cobranca.id),
            provider=cobranca.provider,
            valor=str(cobranca.valor),
        )
        return cobranca

    async def processar_webhook(
        self,
        session: AsyncSession,
        *,
        provider_externo_id: str,
        status: str,
    ) -> CobrancaConsulta:
        """Idempotente — webhook duplicado vira no-op.

        Usado por endpoint ``POST /v1/webhooks/pagamento`` que recebe
        notificação do provider. Em prod, a assinatura HMAC do provider é
        validada antes de chamar este método (não duplicamos aqui — endpoint
        cuida da autenticação).
        """
        if status not in ("paga", "falhou", "cancelada"):
            raise CobrancaInvalida(
                f"Status inválido no webhook: {status!r}"
            )
        cobranca = await self._buscar_por_externo_id(session, provider_externo_id)
        if cobranca is None:
            raise CobrancaNaoEncontrada(
                f"Cobrança com provider_externo_id={provider_externo_id!r} não existe"
            )

        if cobranca.status == status:
            # Webhook repetido — log e segue (no-op).
            log.info(
                "marketplace.webhook.duplicado_ignorado",
                cobranca_id=str(cobranca.id),
                status=status,
            )
            return cobranca

        # Transições terminais não voltam (paga/cancelada são finais).
        if cobranca.status in ("paga", "cancelada"):
            raise CobrancaInvalida(
                f"Cobrança em estado terminal {cobranca.status!r} — "
                "transição para {status!r} bloqueada"
            )

        agora = datetime.now(tz=_TZ_BR)
        cobranca.status = status
        if status == "paga":
            cobranca.paga_em = agora
            # Propaga para a consulta (fato visível no dashboard do parceiro).
            consulta = await session.get(ConsultaMarketplace, cobranca.consulta_id)
            if consulta is not None:
                consulta.paga_em = agora
        elif status == "cancelada":
            cobranca.cancelada_em = agora

        await session.commit()
        await session.refresh(cobranca)

        log.info(
            "marketplace.webhook.processado",
            cobranca_id=str(cobranca.id),
            status=status,
        )
        return cobranca

    @staticmethod
    async def _buscar_por_idem_key(
        session: AsyncSession, idem_key: UUID
    ) -> CobrancaConsulta | None:
        """Gate primário de idempotência — usa a UNIQUE(idempotency_key) (§8.9)."""
        from sqlalchemy import select

        stmt = select(CobrancaConsulta).where(
            CobrancaConsulta.idempotency_key == idem_key
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _buscar_por_consulta(
        session: AsyncSession, consulta_id: UUID
    ) -> CobrancaConsulta | None:
        from sqlalchemy import select

        stmt = select(CobrancaConsulta).where(
            CobrancaConsulta.consulta_id == consulta_id
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _buscar_por_externo_id(
        session: AsyncSession, provider_externo_id: str
    ) -> CobrancaConsulta | None:
        from sqlalchemy import select

        stmt = select(CobrancaConsulta).where(
            CobrancaConsulta.provider_externo_id == provider_externo_id
        )
        return (await session.execute(stmt)).scalar_one_or_none()
