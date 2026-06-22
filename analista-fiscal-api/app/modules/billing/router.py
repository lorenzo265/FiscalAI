"""Endpoints REST — billing/assinatura (Marco 2).

  * ``GET  /v1/billing/planos`` — catálogo (público).
  * ``POST /v1/billing/assinar`` — inicia trial + sessão de checkout.
  * ``GET  /v1/billing/assinatura`` — status da assinatura do tenant.
  * ``POST /v1/billing/cancelar`` — cancela a assinatura.
  * ``POST /v1/webhooks/stripe`` — sync de status (assinatura Stripe validada).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.config import Settings
from app.modules.billing.planos import todos_os_planos
from app.modules.billing.repo import AssinaturaRepo
from app.modules.billing.schemas import (
    AssinaturaOut,
    IniciarAssinaturaIn,
    PlanoOut,
)
from app.modules.billing.service import BillingService
from app.shared.db.deps import SessionDep, TenantDep, WebhookSessionDep
from app.shared.db.models import Assinatura
from app.shared.exceptions import AssinaturaNaoEncontrada

router = APIRouter(prefix="/v1/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/v1/webhooks", tags=["billing-webhooks"])


def _service(request: Request) -> BillingService:
    settings: Settings = request.app.state.settings
    return BillingService(settings)


def _to_out(a: Assinatura) -> AssinaturaOut:
    return AssinaturaOut(
        id=a.id,
        plano_codigo=a.plano_codigo,
        status=a.status,
        trial_ends_at=a.trial_ends_at,
        current_period_end=a.current_period_end,
        checkout_url=a.checkout_url,
    )


@router.get(
    "/planos", response_model=list[PlanoOut], summary="Catálogo de planos"
)
async def listar_planos() -> list[PlanoOut]:
    return [
        PlanoOut(
            codigo=p.codigo,
            nome=p.nome,
            preco_mensal=p.preco_mensal,
            descricao=p.descricao,
            max_empresas=p.max_empresas,
        )
        for p in todos_os_planos()
    ]


@router.post(
    "/assinar",
    response_model=AssinaturaOut,
    summary="Inicia assinatura (trial 14 dias + checkout Stripe)",
)
async def assinar(
    request: Request,
    ctx: TenantDep,
    session: SessionDep,
    payload: IniciarAssinaturaIn,
) -> AssinaturaOut:
    assinatura = await _service(request).iniciar_assinatura(
        session, tenant_id=ctx.tenant_id, plano_codigo=payload.plano_codigo
    )
    return _to_out(assinatura)


@router.get(
    "/assinatura",
    response_model=AssinaturaOut,
    summary="Assinatura atual do tenant",
)
async def minha_assinatura(ctx: TenantDep, session: SessionDep) -> AssinaturaOut:
    assinatura = await AssinaturaRepo(session).ativa_do_tenant(ctx.tenant_id)
    if assinatura is None:
        raise AssinaturaNaoEncontrada("Nenhuma assinatura ativa para este tenant")
    return _to_out(assinatura)


@router.post(
    "/cancelar", response_model=AssinaturaOut, summary="Cancela a assinatura"
)
async def cancelar(
    request: Request, ctx: TenantDep, session: SessionDep
) -> AssinaturaOut:
    assinatura = await _service(request).cancelar_assinatura(
        session, tenant_id=ctx.tenant_id
    )
    return _to_out(assinatura)


@webhook_router.post(
    "/stripe", summary="Webhook do Stripe — sincroniza status da assinatura"
)
async def webhook_stripe(
    request: Request,
    session: WebhookSessionDep,
    stripe_signature: Annotated[
        str | None, Header(alias="Stripe-Signature")
    ] = None,
) -> dict[str, str]:
    """Lê o body bruto, valida a assinatura no provider e sincroniza o status.

    A sessão é superuser (bypassa RLS) — o Stripe não conhece o tenant; a
    autenticação é a assinatura ``Stripe-Signature`` (validada antes de tudo).
    """
    body = await request.body()
    await _service(request).processar_webhook(
        session, payload=body, assinatura_header=stripe_signature
    )
    return {"status": "ok"}
