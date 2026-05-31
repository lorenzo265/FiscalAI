"""Golden tests — calcula_darf_lp.py (Sprint 20 PR1).

Princípio §8.4: golden tests bloqueiam merge.
Cada caso cobre: código de receita, vencimento, valor, fundamento legal.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.lucro_presumido.calcula_darf_lp import (
    ALGORITMO_VERSAO,
    calcular_darf_cofins,
    calcular_darf_csll,
    calcular_darf_irpj,
    calcular_darf_pis,
)


# ── IRPJ ─────────────────────────────────────────────────────────────────────


def test_darf_irpj_t1_2026_codigo_e_vencimento() -> None:
    """T1/2026: competência 01/01/2026, vencimento 30/04/2026."""
    r = calcular_darf_irpj(Decimal("5000.00"), 2026, 1)
    assert r.codigo_receita == "2089"
    assert r.competencia == date(2026, 1, 1)
    assert r.data_vencimento == date(2026, 4, 30)
    assert r.periodo_apuracao == "2026-T1"


def test_darf_irpj_t2_2026_vencimento() -> None:
    """T2/2026: competência 01/04/2026, vencimento 31/07/2026."""
    r = calcular_darf_irpj(Decimal("8000.00"), 2026, 2)
    assert r.competencia == date(2026, 4, 1)
    assert r.data_vencimento == date(2026, 7, 31)
    assert r.periodo_apuracao == "2026-T2"


def test_darf_irpj_t3_2026_vencimento() -> None:
    """T3/2026: competência 01/07/2026, vencimento 31/10/2026."""
    r = calcular_darf_irpj(Decimal("6500.00"), 2026, 3)
    assert r.competencia == date(2026, 7, 1)
    assert r.data_vencimento == date(2026, 10, 31)
    assert r.periodo_apuracao == "2026-T3"


def test_darf_irpj_t4_2026_vencimento_ano_seguinte() -> None:
    """T4/2026: competência 01/10/2026, vencimento 31/01/2027."""
    r = calcular_darf_irpj(Decimal("12000.00"), 2026, 4)
    assert r.competencia == date(2026, 10, 1)
    assert r.data_vencimento == date(2027, 1, 31)
    assert r.periodo_apuracao == "2026-T4"


def test_darf_irpj_valor_zero_permitido() -> None:
    """IRPJ zerado é válido (IRRF compensou totalmente)."""
    r = calcular_darf_irpj(Decimal("0.00"), 2026, 1)
    assert r.valor_principal == Decimal("0.00")
    assert r.total == Decimal("0.00")


def test_darf_irpj_com_juros_e_multa() -> None:
    """total = principal + juros + multa (pagamento em atraso)."""
    r = calcular_darf_irpj(
        Decimal("1000.00"),
        2026,
        1,
        juros=Decimal("10.50"),
        multa=Decimal("20.00"),
    )
    assert r.valor_principal == Decimal("1000.00")
    assert r.juros == Decimal("10.50")
    assert r.multa == Decimal("20.00")
    assert r.total == Decimal("1030.50")


def test_darf_irpj_algoritmo_versao() -> None:
    r = calcular_darf_irpj(Decimal("500.00"), 2026, 1)
    assert r.algoritmo_versao == ALGORITMO_VERSAO


def test_darf_irpj_fundamento_legal_preenchido() -> None:
    r = calcular_darf_irpj(Decimal("500.00"), 2026, 1)
    assert "Lei 9.430" in r.fundamento_legal


def test_darf_irpj_valor_negativo_levanta_erro() -> None:
    with pytest.raises(ValueError, match="negativo"):
        calcular_darf_irpj(Decimal("-1.00"), 2026, 1)


def test_darf_irpj_trimestre_invalido_levanta_erro() -> None:
    with pytest.raises(ValueError, match="1, 2, 3 ou 4"):
        calcular_darf_irpj(Decimal("1000.00"), 2026, 5)


def test_darf_irpj_trimestre_zero_levanta_erro() -> None:
    with pytest.raises(ValueError, match="1, 2, 3 ou 4"):
        calcular_darf_irpj(Decimal("1000.00"), 2026, 0)


# ── CSLL ─────────────────────────────────────────────────────────────────────


def test_darf_csll_t1_2026_codigo_e_vencimento() -> None:
    """CSLL T1/2026: código 2372, mesmo vencimento do IRPJ."""
    r = calcular_darf_csll(Decimal("3000.00"), 2026, 1)
    assert r.codigo_receita == "2372"
    assert r.competencia == date(2026, 1, 1)
    assert r.data_vencimento == date(2026, 4, 30)
    assert r.periodo_apuracao == "2026-T1"


def test_darf_csll_t4_2026_vencimento_ano_seguinte() -> None:
    r = calcular_darf_csll(Decimal("4000.00"), 2026, 4)
    assert r.data_vencimento == date(2027, 1, 31)


def test_darf_csll_zero_permitido() -> None:
    r = calcular_darf_csll(Decimal("0.00"), 2026, 2)
    assert r.valor_principal == Decimal("0.00")
    assert r.total == Decimal("0.00")


def test_darf_csll_denominacao_identifica_tributo() -> None:
    r = calcular_darf_csll(Decimal("500.00"), 2026, 1)
    assert "CSLL" in r.denominacao


def test_darf_csll_negativo_levanta_erro() -> None:
    with pytest.raises(ValueError, match="negativo"):
        calcular_darf_csll(Decimal("-0.01"), 2026, 1)


# ── PIS ──────────────────────────────────────────────────────────────────────


def test_darf_pis_jan_2026_codigo_e_vencimento() -> None:
    """PIS jan/2026: código 8109, vencimento 25/02/2026."""
    r = calcular_darf_pis(Decimal("735.00"), date(2026, 1, 1))
    assert r.codigo_receita == "8109"
    assert r.competencia == date(2026, 1, 1)
    assert r.data_vencimento == date(2026, 2, 25)
    assert r.periodo_apuracao == "2026-01"


def test_darf_pis_dez_2026_vencimento_jan_2027() -> None:
    """PIS dez/2026: vencimento 25/01/2027 (ano seguinte)."""
    r = calcular_darf_pis(Decimal("900.00"), date(2026, 12, 1))
    assert r.data_vencimento == date(2027, 1, 25)
    assert r.periodo_apuracao == "2026-12"


def test_darf_pis_zero_permitido() -> None:
    r = calcular_darf_pis(Decimal("0.00"), date(2026, 3, 1))
    assert r.total == Decimal("0.00")


def test_darf_pis_competencia_nao_primeiro_dia_levanta_erro() -> None:
    with pytest.raises(ValueError, match="primeiro dia"):
        calcular_darf_pis(Decimal("100.00"), date(2026, 1, 15))


def test_darf_pis_denominacao_identifica_tributo() -> None:
    r = calcular_darf_pis(Decimal("200.00"), date(2026, 1, 1))
    assert "PIS" in r.denominacao


# ── Cofins ───────────────────────────────────────────────────────────────────


def test_darf_cofins_jan_2026_codigo_e_vencimento() -> None:
    """Cofins jan/2026: código 2172, vencimento 25/02/2026."""
    r = calcular_darf_cofins(Decimal("3402.00"), date(2026, 1, 1))
    assert r.codigo_receita == "2172"
    assert r.competencia == date(2026, 1, 1)
    assert r.data_vencimento == date(2026, 2, 25)
    assert r.periodo_apuracao == "2026-01"


def test_darf_cofins_dez_2026_vencimento_jan_2027() -> None:
    r = calcular_darf_cofins(Decimal("4100.00"), date(2026, 12, 1))
    assert r.data_vencimento == date(2027, 1, 25)


def test_darf_cofins_zero_permitido() -> None:
    r = calcular_darf_cofins(Decimal("0.00"), date(2026, 6, 1))
    assert r.valor_principal == Decimal("0.00")


def test_darf_cofins_denominacao_identifica_tributo() -> None:
    r = calcular_darf_cofins(Decimal("500.00"), date(2026, 1, 1))
    assert "Cofins" in r.denominacao


# ── Invariantes ──────────────────────────────────────────────────────────────


def test_darf_irpj_total_quantizado_round_half_even() -> None:
    """total com casas ímpares arredonda para o centavo mais próximo."""
    r = calcular_darf_irpj(
        Decimal("1000.00"),
        2026,
        1,
        juros=Decimal("0.005"),
    )
    # 1000.005 → ROUND_HALF_EVEN → 1000.00 (5 no dígito 3 com dígito 2=0 → arredonda pra baixo)
    assert r.total == Decimal("1000.00")


def test_darf_pis_total_quantizado() -> None:
    r = calcular_darf_pis(
        Decimal("1000.00"),
        date(2026, 1, 1),
        juros=Decimal("0.005"),
    )
    assert r.total == Decimal("1000.00")


def test_darf_irpj_codigo_receita_diferente_de_csll() -> None:
    irpj = calcular_darf_irpj(Decimal("1000.00"), 2026, 1)
    csll = calcular_darf_csll(Decimal("1000.00"), 2026, 1)
    assert irpj.codigo_receita != csll.codigo_receita
    assert irpj.data_vencimento == csll.data_vencimento  # mesmo vencimento


def test_darf_pis_e_cofins_mesmo_vencimento() -> None:
    pis = calcular_darf_pis(Decimal("500.00"), date(2026, 3, 1))
    cofins = calcular_darf_cofins(Decimal("2300.00"), date(2026, 3, 1))
    assert pis.data_vencimento == cofins.data_vencimento
    assert pis.data_vencimento == date(2026, 4, 25)
