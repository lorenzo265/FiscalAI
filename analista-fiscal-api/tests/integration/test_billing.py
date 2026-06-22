"""Integração — billing/assinatura ponta a ponta (Marco 2).

Fluxo real (router → service → repo → Postgres) com o ``_FakeBillingProvider``
(sem STRIPE_SECRET_KEY no ambiente de teste). Requer Postgres + alembic head.

IDs de evento/subscription são únicos por execução: o DB de dev não reseta
entre rodadas, e ``evento_billing.stripe_event_id`` / ``stripe_subscription_id``
são UNIQUE — IDs fixos colidiriam (webhook viraria no-op).
"""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _registrar(client: AsyncClient) -> str:
    slug = f"t{uuid.uuid4().hex[:10]}"
    r = await client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Billing",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["access_token"])


async def _post_webhook(client: AsyncClient, evento: dict[str, object]) -> None:
    r = await client.post("/v1/webhooks/stripe", content=json.dumps(evento))
    assert r.status_code == 200, r.text


async def test_fluxo_assinatura_completo(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    h = {"Authorization": f"Bearer {token}"}
    run = uuid.uuid4().hex[:8]
    sub = f"sub_{run}"

    # 1. Assinar — cria trial + checkout_url.
    r = await live_client.post(
        "/v1/billing/assinar", json={"plano_codigo": "essencial"}, headers=h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "trial"
    assert body["checkout_url"]
    assinatura_id = body["id"]

    # 2. Idempotência — 2ª chamada devolve a MESMA assinatura.
    r2 = await live_client.post(
        "/v1/billing/assinar", json={"plano_codigo": "profissional"}, headers=h
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == assinatura_id

    # 3. Webhook checkout.session.completed → ativa.
    await _post_webhook(
        live_client,
        {
            "id": f"evt_checkout_{run}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": assinatura_id,
                    "subscription": sub,
                    "customer": f"cus_{run}",
                }
            },
        },
    )
    r = await live_client.get("/v1/billing/assinatura", headers=h)
    assert r.json()["status"] == "ativa"

    # 4. Webhook invoice.payment_failed → inadimplente.
    await _post_webhook(
        live_client,
        {
            "id": f"evt_fail_{run}",
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": sub, "id": f"in_{run}"}},
        },
    )
    r = await live_client.get("/v1/billing/assinatura", headers=h)
    assert r.json()["status"] == "inadimplente"

    # 5. Webhook customer.subscription.deleted → cancelada (terminal).
    await _post_webhook(
        live_client,
        {
            "id": f"evt_del_{run}",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": sub}},
        },
    )
    # cancelada não aparece mais em /assinatura (só vivas) → 404.
    r = await live_client.get("/v1/billing/assinatura", headers=h)
    assert r.status_code == 404

    # 6. Webhook duplicado (mesmo stripe_event_id) → no-op (200, sem efeito).
    await _post_webhook(
        live_client,
        {
            "id": f"evt_del_{run}",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": sub}},
        },
    )


async def test_planos_publico(live_client: AsyncClient) -> None:
    r = await live_client.get("/v1/billing/planos")
    assert r.status_code == 200
    codigos = {p["codigo"] for p in r.json()}
    assert codigos == {"essencial", "profissional", "avancado"}
