"""Golden — catálogo de planos de billing (Marco 2)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.billing.planos import (
    PLANOS_VERSAO,
    TRIAL_DIAS,
    plano_para,
    todos_os_planos,
)
from app.shared.exceptions import PlanoInexistente


def test_tres_planos_com_precos_corretos() -> None:
    planos = {p.codigo: p for p in todos_os_planos()}
    assert set(planos) == {"essencial", "profissional", "avancado"}
    assert planos["essencial"].preco_mensal == Decimal("149.00")
    assert planos["profissional"].preco_mensal == Decimal("299.00")
    assert planos["avancado"].preco_mensal == Decimal("499.00")


def test_max_empresas_por_plano() -> None:
    planos = {p.codigo: p for p in todos_os_planos()}
    assert planos["essencial"].max_empresas == 1
    assert planos["profissional"].max_empresas == 1
    assert planos["avancado"].max_empresas == 5


def test_trial_14_dias_e_versao_setada() -> None:
    assert TRIAL_DIAS == 14
    assert PLANOS_VERSAO  # não vazio


def test_cada_plano_referencia_uma_env_de_price() -> None:
    for p in todos_os_planos():
        assert p.stripe_price_env.startswith("STRIPE_PRICE_")


def test_plano_para_resolve() -> None:
    assert plano_para("essencial").nome == "Essencial"


def test_plano_inexistente_levanta() -> None:
    with pytest.raises(PlanoInexistente):
        plano_para("inexistente")
