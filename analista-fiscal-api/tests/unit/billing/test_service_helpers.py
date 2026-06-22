"""Golden — helpers puros + máquina de estados do BillingService (Marco 2).

Cobre a lógica de dinheiro/estado sem DB: conversão de centavos, coerções, e
a transição com guard anti-revival (cancelada é terminal).
"""
from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

from app.modules.billing.service import (
    BillingService,
    _cents_para_decimal,
    _epoch_para_dt,
    _str_ou_none,
)
from app.shared.db.models import Assinatura


def _assinatura(status: str) -> Assinatura:
    return Assinatura(
        tenant_id=None,
        plano_codigo="essencial",
        status=status,
        planos_versao="x",
    )


def test_cents_para_decimal() -> None:
    assert _cents_para_decimal(14900) == Decimal("149.00")
    assert _cents_para_decimal(100) == Decimal("1.00")
    assert _cents_para_decimal(0) == Decimal("0.00")
    # bool não é valor monetário válido → 0
    assert _cents_para_decimal(True) == Decimal("0.00")
    assert _cents_para_decimal(None) == Decimal("0.00")


def test_str_ou_none() -> None:
    assert _str_ou_none("sub_1") == "sub_1"
    assert _str_ou_none("") is None
    assert _str_ou_none(None) is None


def test_epoch_para_dt() -> None:
    dt = _epoch_para_dt(1_767_225_600)  # 2026-01-01 (epoch)
    assert dt is not None
    assert dt.tzinfo == ZoneInfo("America/Sao_Paulo")
    assert _epoch_para_dt(None) is None
    assert _epoch_para_dt(True) is None  # bool não é epoch


def test_transicao_trial_para_ativa() -> None:
    a = _assinatura("trial")
    BillingService._transicionar(a, "ativa")
    assert a.status == "ativa"


def test_transicao_ativa_para_inadimplente_e_volta() -> None:
    a = _assinatura("ativa")
    BillingService._transicionar(a, "inadimplente")
    assert a.status == "inadimplente"
    BillingService._transicionar(a, "ativa")
    assert a.status == "ativa"


def test_cancelada_e_terminal_nao_revive() -> None:
    a = _assinatura("cancelada")
    BillingService._transicionar(a, "ativa")
    assert a.status == "cancelada"  # guard anti-revival
