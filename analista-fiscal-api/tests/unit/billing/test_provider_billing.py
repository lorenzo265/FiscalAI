"""Golden — _FakeBillingProvider (Marco 2). Sem Stripe, sem DB."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.modules.billing.planos import plano_para
from app.modules.billing.provider import _FakeBillingProvider
from app.shared.exceptions import WebhookStripeAssinaturaInvalida


@pytest.mark.asyncio
async def test_fake_checkout_url_deterministico() -> None:
    aid = uuid4()
    out = await _FakeBillingProvider().criar_checkout(
        assinatura_id=aid, plano=plano_para("essencial"), stripe_customer_id=None
    )
    assert out.provider == "fake"
    assert out.checkout_url == f"https://fiscalai.local/checkout/{aid}"
    assert out.stripe_customer_id is not None


def test_fake_parse_evento_json_valido() -> None:
    payload = json.dumps(
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {"object": {"subscription": "sub_1", "customer": "cus_1"}},
        }
    ).encode()
    ev = _FakeBillingProvider().parse_evento(payload=payload, assinatura_header=None)
    assert ev.stripe_event_id == "evt_1"
    assert ev.tipo == "checkout.session.completed"
    assert ev.dados["subscription"] == "sub_1"


def test_fake_parse_evento_json_invalido_levanta() -> None:
    with pytest.raises(WebhookStripeAssinaturaInvalida):
        _FakeBillingProvider().parse_evento(payload=b"nao-eh-json", assinatura_header=None)


def test_fake_parse_evento_formato_errado_levanta() -> None:
    with pytest.raises(WebhookStripeAssinaturaInvalida):
        _FakeBillingProvider().parse_evento(
            payload=json.dumps({"id": "evt_1"}).encode(), assinatura_header=None
        )
