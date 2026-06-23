"""Golden tests — regras_lp.py (Sprint 20 PR3).

Princípio §8.4: golden tests bloqueiam merge.
Cada caso cobre: regra ativada/não-ativada, severidade, campos obrigatórios.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.advisor.regras_lp import (
    ALGORITMO_VERSAO,
    DarfLpInfo,
    checar_darf_lp_vencidas,
    checar_distribuicao_isenta_potencial,
    checar_irpj_adicional,
    checar_limite_receita_lp,
)

# ── Regra 1: DARF vencida ─────────────────────────────────────────────────────


def test_darf_vencida_retorna_sugestao_alta():
    guia = DarfLpInfo(
        codigo_receita="2089",
        denominacao="IRPJ",
        data_vencimento=date(2026, 4, 30),
        status="a_pagar",
        valor=Decimal("5000.00"),
        periodo_apuracao="2026-T1",
    )
    resultado = checar_darf_lp_vencidas([guia], hoje=date(2026, 6, 1))
    assert len(resultado) == 1
    assert resultado[0].severidade == "alta"
    assert resultado[0].codigo == "darf_lp_vencida_2089"


def test_darf_vencida_dias_atraso_correto():
    guia = DarfLpInfo(
        codigo_receita="2372",
        denominacao="CSLL",
        data_vencimento=date(2026, 4, 30),
        status="a_pagar",
        valor=Decimal("3000.00"),
        periodo_apuracao="2026-T1",
    )
    resultado = checar_darf_lp_vencidas([guia], hoje=date(2026, 5, 30))
    assert "30 dias" in resultado[0].titulo


def test_darf_vencida_paga_nao_gera_sugestao():
    guia = DarfLpInfo(
        codigo_receita="2089",
        denominacao="IRPJ",
        data_vencimento=date(2026, 4, 30),
        status="pago",
        valor=Decimal("5000.00"),
        periodo_apuracao="2026-T1",
    )
    assert checar_darf_lp_vencidas([guia], hoje=date(2026, 6, 1)) == []


def test_darf_vencimento_futuro_nao_gera_sugestao():
    guia = DarfLpInfo(
        codigo_receita="2089",
        denominacao="IRPJ",
        data_vencimento=date(2026, 7, 31),
        status="a_pagar",
        valor=Decimal("5000.00"),
        periodo_apuracao="2026-T2",
    )
    assert checar_darf_lp_vencidas([guia], hoje=date(2026, 6, 1)) == []


def test_darf_multiplas_vencidas_gera_multiplas_sugestoes():
    guias = [
        DarfLpInfo("2089", "IRPJ", date(2026, 4, 30), "a_pagar", Decimal("5000"), "2026-T1"),
        DarfLpInfo("2372", "CSLL", date(2026, 4, 30), "a_pagar", Decimal("3000"), "2026-T1"),
        DarfLpInfo("8109", "PIS", date(2026, 2, 25), "a_pagar", Decimal("500"), "2026-01"),
    ]
    resultado = checar_darf_lp_vencidas(guias, hoje=date(2026, 6, 1))
    assert len(resultado) == 3


def test_darf_vencida_fonte_norma_preenchida():
    guia = DarfLpInfo(
        codigo_receita="2172",
        denominacao="Cofins",
        data_vencimento=date(2026, 2, 25),
        status="a_pagar",
        valor=Decimal("9000.00"),
        periodo_apuracao="2026-01",
    )
    r = checar_darf_lp_vencidas([guia], hoje=date(2026, 4, 1))
    assert "Lei 9.430" in r[0].fonte_norma


def test_darf_lista_vazia_sem_sugestao():
    assert checar_darf_lp_vencidas([], hoje=date(2026, 6, 1)) == []


# ── Regra 2: IRPJ adicional ──────────────────────────────────────────────────


def test_irpj_adicional_ativado_gera_sugestao():
    r = checar_irpj_adicional(
        irpj_adicional=Decimal("10000.00"),
        base_total=Decimal("160000.00"),
        limite_adicional=Decimal("60000.00"),
        trimestre=1,
        ano=2026,
    )
    assert r is not None
    assert r.severidade == "media"
    assert r.codigo == "irpj_adicional_ativado"


def test_irpj_adicional_zero_sem_sugestao():
    r = checar_irpj_adicional(
        irpj_adicional=Decimal("0.00"),
        base_total=Decimal("40000.00"),
        limite_adicional=Decimal("60000.00"),
        trimestre=1,
        ano=2026,
    )
    assert r is None


def test_irpj_adicional_trimestre_no_titulo():
    r = checar_irpj_adicional(
        irpj_adicional=Decimal("5000.00"),
        base_total=Decimal("110000.00"),
        limite_adicional=Decimal("60000.00"),
        trimestre=3,
        ano=2026,
    )
    assert r is not None
    assert "T3/2026" in r.titulo


def test_irpj_adicional_fonte_norma():
    r = checar_irpj_adicional(
        Decimal("1000"), Decimal("70000"), Decimal("60000"), 2, 2026
    )
    assert r is not None
    assert "Lei 9.249" in r.fonte_norma


def test_irpj_adicional_economia_anual_proxy_4x():
    r = checar_irpj_adicional(
        Decimal("3000"), Decimal("90000"), Decimal("60000"), 1, 2026
    )
    assert r is not None
    assert r.economia_anual_estimada == Decimal("12000.00")


# ── Regra 3: Distribuição isenta ─────────────────────────────────────────────


def test_distribuicao_disponivel_gera_sugestao():
    r = checar_distribuicao_isenta_potencial(
        limite_isento=Decimal("50000.00"),
        total_distribuido=Decimal("10000.00"),
    )
    assert r is not None
    assert r.codigo == "distribuicao_isenta_disponivel"
    assert r.severidade == "informativa"


def test_distribuicao_margem_abaixo_limiar_sem_sugestao():
    r = checar_distribuicao_isenta_potencial(
        limite_isento=Decimal("10000.00"),
        total_distribuido=Decimal("9500.00"),
    )
    assert r is None  # disponível = R$ 500 < limiar de R$ 5.000


def test_distribuicao_limite_zero_sem_sugestao():
    r = checar_distribuicao_isenta_potencial(
        limite_isento=Decimal("0.00"),
        total_distribuido=Decimal("0.00"),
    )
    assert r is None


def test_distribuicao_disponivel_correto_nos_detalhes():
    r = checar_distribuicao_isenta_potencial(
        limite_isento=Decimal("30000.00"),
        total_distribuido=Decimal("5000.00"),
    )
    assert r is not None
    assert r.detalhes["disponivel"] == "25000.00"


def test_distribuicao_fonte_norma():
    r = checar_distribuicao_isenta_potencial(Decimal("20000"), Decimal("0"))
    assert r is not None
    assert "Lei 9.249" in r.fonte_norma and "art. 10" in r.fonte_norma


# ── Regra 4: Teto receita LP ─────────────────────────────────────────────────


def test_receita_acima_90pct_teto_gera_media():
    r = checar_limite_receita_lp(Decimal("72_000_000.00"))  # ~92% de R$78M
    assert r is not None
    assert r.severidade == "media"


def test_receita_acima_95pct_teto_gera_alta():
    r = checar_limite_receita_lp(Decimal("75_000_000.00"))  # ~96% de R$78M
    assert r is not None
    assert r.severidade == "alta"


def test_receita_abaixo_90pct_sem_sugestao():
    r = checar_limite_receita_lp(Decimal("50_000_000.00"))
    assert r is None


def test_receita_teto_fonte_norma():
    r = checar_limite_receita_lp(Decimal("74_000_000.00"))
    assert r is not None
    assert "RIR/2018" in r.fonte_norma


def test_receita_teto_algoritmo_versao():
    r = checar_limite_receita_lp(Decimal("73_000_000.00"))
    assert r is not None
    assert r.algoritmo_versao == ALGORITMO_VERSAO
