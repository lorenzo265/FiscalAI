"""Provider de billing — Stripe real (atrás de env) + fake para dev/teste.

Espelha o padrão do marketplace (Protocol + _Fake + factory). O
``StripeProvider`` importa o SDK ``stripe`` LAZY (grupo opcional ``billing``);
sem ``STRIPE_SECRET_KEY`` ou sem o pacote, a factory cai no
``_FakeBillingProvider``. Nunca há mock em produção: a credencial liga o real.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import structlog

from app.config import Settings
from app.modules.billing.planos import Plano
from app.shared.exceptions import WebhookStripeAssinaturaInvalida

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CheckoutCriado:
    """Saída de ``criar_checkout`` — link de pagamento + customer."""

    provider: str
    checkout_url: str
    stripe_customer_id: str | None


@dataclass(frozen=True, slots=True)
class EventoStripe:
    """Evento de webhook já validado e parseado."""

    stripe_event_id: str
    tipo: str
    dados: dict[str, object]  # event.data.object (sem Any)


class BillingProvider(Protocol):
    """Contrato mínimo de um gateway de assinatura (Stripe/Pagar.me/...)."""

    nome: str

    async def criar_checkout(
        self,
        *,
        assinatura_id: UUID,
        plano: Plano,
        stripe_customer_id: str | None,
    ) -> CheckoutCriado:
        """Cria a sessão de checkout (assinatura) e devolve o link."""
        ...

    async def cancelar(self, *, stripe_subscription_id: str) -> None:
        """Cancela a assinatura no gateway."""
        ...

    def parse_evento(
        self, *, payload: bytes, assinatura_header: str | None
    ) -> EventoStripe:
        """Valida a assinatura do webhook e devolve o evento parseado.

        Levanta ``WebhookStripeAssinaturaInvalida`` se a assinatura não confere.
        """
        ...


class StripeProvider:
    """Gateway real Stripe. SDK importado lazy (grupo opcional ``billing``)."""

    nome: str = "stripe"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def criar_checkout(
        self,
        *,
        assinatura_id: UUID,
        plano: Plano,
        stripe_customer_id: str | None,
    ) -> CheckoutCriado:
        import stripe

        stripe.api_key = self._settings.STRIPE_SECRET_KEY
        price_id = str(getattr(self._settings, plano.stripe_price_env, "") or "")
        if not price_id:
            log.warning(
                "billing.stripe.price_ausente",
                plano=plano.codigo,
                env=plano.stripe_price_env,
            )
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=stripe_customer_id or None,
            client_reference_id=str(assinatura_id),
            metadata={"assinatura_id": str(assinatura_id), "plano": plano.codigo},
            success_url=self._settings.BILLING_CHECKOUT_SUCCESS_URL,
            cancel_url=self._settings.BILLING_CHECKOUT_CANCEL_URL,
        )
        return CheckoutCriado(
            provider=self.nome,
            checkout_url=str(session.url),
            stripe_customer_id=(
                str(session.customer) if session.customer else stripe_customer_id
            ),
        )

    async def cancelar(self, *, stripe_subscription_id: str) -> None:
        import stripe

        stripe.api_key = self._settings.STRIPE_SECRET_KEY
        stripe.Subscription.cancel(stripe_subscription_id)

    def parse_evento(
        self, *, payload: bytes, assinatura_header: str | None
    ) -> EventoStripe:
        import stripe

        if not assinatura_header:
            raise WebhookStripeAssinaturaInvalida(
                "Header Stripe-Signature ausente — webhook rejeitado"
            )
        try:
            event = stripe.Webhook.construct_event(
                payload, assinatura_header, self._settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:  # SignatureVerificationError, ValueError, etc.
            raise WebhookStripeAssinaturaInvalida(
                "Assinatura do webhook Stripe inválida — rejeitado"
            ) from exc
        obj = dict(event["data"]["object"])
        return EventoStripe(
            stripe_event_id=str(event["id"]),
            tipo=str(event["type"]),
            dados=obj,
        )


class _FakeBillingProvider:
    """Provider de mentira (dev/teste sem Stripe). Checkout determinístico.

    ``parse_evento`` aceita um JSON simples no payload (os testes constroem):
    ``{"id": "...", "type": "...", "data": {"object": {...}}}``. Sem verificação
    de assinatura — em prod, a factory escolhe o ``StripeProvider`` real.
    """

    nome: str = "fake"

    async def criar_checkout(
        self,
        *,
        assinatura_id: UUID,
        plano: Plano,
        stripe_customer_id: str | None,
    ) -> CheckoutCriado:
        return CheckoutCriado(
            provider=self.nome,
            checkout_url=f"https://fiscalai.local/checkout/{assinatura_id}",
            stripe_customer_id=stripe_customer_id or f"cus_fake_{assinatura_id.hex[:12]}",
        )

    async def cancelar(self, *, stripe_subscription_id: str) -> None:
        log.info("billing.fake.cancelar", stripe_subscription_id=stripe_subscription_id)

    def parse_evento(
        self, *, payload: bytes, assinatura_header: str | None
    ) -> EventoStripe:
        try:
            raw = json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise WebhookStripeAssinaturaInvalida(
                "Payload do webhook não é JSON válido"
            ) from exc
        try:
            obj = dict(raw["data"]["object"])
            return EventoStripe(
                stripe_event_id=str(raw["id"]),
                tipo=str(raw["type"]),
                dados=obj,
            )
        except (KeyError, TypeError) as exc:
            raise WebhookStripeAssinaturaInvalida(
                "Payload do webhook fora do formato esperado"
            ) from exc


def build_billing_provider(settings: Settings) -> BillingProvider:
    """Stripe real se ``STRIPE_SECRET_KEY`` setado E o SDK instalado; senão fake."""
    if settings.STRIPE_SECRET_KEY:
        try:
            import stripe  # noqa: F401
        except ImportError:
            log.warning("billing.stripe.sdk_ausente_usando_fake")
            return _FakeBillingProvider()
        return StripeProvider(settings)
    return _FakeBillingProvider()
