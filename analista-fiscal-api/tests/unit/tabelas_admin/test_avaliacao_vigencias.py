"""Testes dos avaliadores puros §8.6 (Sprint 19.5 PR2).

Cada avaliador é puro (sem I/O) — golden test direto, sem mock.
"""

from __future__ import annotations

from datetime import date

from app.modules.tabelas_admin.avaliacao_vigencias import (
    TIPO_FUTURA_PROXIMA,
    TIPO_PROXIMA_VENCER,
    TIPO_VENCIDA,
    avaliar_cbs_ibs,
    avaliar_fgts,
    avaliar_icms_uf,
    avaliar_inss_irrf,
    avaliar_presuncao_lp,
    avaliar_simples_nacional,
)

# ── INSS / IRRF ─────────────────────────────────────────────────────────────


def test_inss_marco_2026_com_vigencia_2025_eh_critico() -> None:
    r = avaliar_inss_irrf(
        tipo_tabela="inss",
        valid_from_ativa=date(2025, 1, 1),
        hoje=date(2026, 3, 15),
    )
    assert r.deve_alertar
    assert r.severidade == "critico"
    assert r.tipo == TIPO_VENCIDA
    assert r.contexto["tipo_tabela"] == "inss"
    assert r.contexto["ano_corrente"] == 2026
    assert r.contexto["ano_vigencia_ativa"] == 2025


def test_inss_janeiro_2026_com_vigencia_2025_nao_alerta() -> None:
    """Janeiro tolerante — Portaria ainda pode estar saindo."""
    r = avaliar_inss_irrf(
        tipo_tabela="inss",
        valid_from_ativa=date(2025, 1, 1),
        hoje=date(2026, 1, 10),
    )
    assert not r.deve_alertar


def test_inss_marco_2027_com_vigencia_2026_eh_critico_outro_ano() -> None:
    """Worker em 2027 sem POST de 2027 cria alerta novo (idempotência por ano)."""
    r = avaliar_inss_irrf(
        tipo_tabela="inss",
        valid_from_ativa=date(2026, 1, 15),
        hoje=date(2027, 4, 1),
    )
    assert r.deve_alertar
    assert r.contexto["ano_corrente"] == 2027
    assert r.contexto["ano_vigencia_ativa"] == 2026


def test_inss_sem_vigencia_eh_sempre_critico() -> None:
    r = avaliar_inss_irrf(
        tipo_tabela="inss", valid_from_ativa=None, hoje=date(2026, 5, 27)
    )
    assert r.deve_alertar
    assert r.severidade == "critico"
    assert "ausente" in r.titulo.lower()


def test_irrf_marco_2026_com_vigencia_2025_eh_critico() -> None:
    r = avaliar_inss_irrf(
        tipo_tabela="irrf",
        valid_from_ativa=date(2025, 1, 1),
        hoje=date(2026, 3, 15),
    )
    assert r.deve_alertar
    assert r.contexto["tipo_tabela"] == "irrf"


# ── FGTS ────────────────────────────────────────────────────────────────────


def test_fgts_vigencia_recente_nao_alerta() -> None:
    r = avaliar_fgts(
        valid_from_ativa=date(2025, 1, 1), hoje=date(2026, 5, 27)
    )
    assert not r.deve_alertar


def test_fgts_vigencia_mais_de_10_anos_info() -> None:
    r = avaliar_fgts(
        valid_from_ativa=date(2010, 1, 1), hoje=date(2026, 5, 27)
    )
    assert r.deve_alertar
    assert r.severidade == "info"
    assert r.tipo == TIPO_PROXIMA_VENCER


# ── Simples Nacional ────────────────────────────────────────────────────────


def test_simples_nacional_mais_de_5_anos_aviso() -> None:
    r = avaliar_simples_nacional(
        valid_from_ativa=date(2018, 1, 1), hoje=date(2026, 5, 27)
    )
    assert r.deve_alertar
    assert r.severidade == "aviso"


def test_simples_nacional_recente_nao_alerta() -> None:
    r = avaliar_simples_nacional(
        valid_from_ativa=date(2024, 1, 1), hoje=date(2026, 5, 27)
    )
    assert not r.deve_alertar


# ── Presunção LP ────────────────────────────────────────────────────────────


def test_presuncao_lp_mais_de_10_anos_info() -> None:
    r = avaliar_presuncao_lp(
        valid_from_ativa=date(2010, 1, 1), hoje=date(2026, 5, 27)
    )
    assert r.deve_alertar
    assert r.severidade == "info"


# ── ICMS UF ─────────────────────────────────────────────────────────────────


def test_icms_uf_mais_de_2_anos_aviso() -> None:
    r = avaliar_icms_uf(
        uf="SP",
        valid_from_ativa=date(2023, 1, 1),
        hoje=date(2026, 5, 27),
    )
    assert r.deve_alertar
    assert r.severidade == "aviso"
    assert r.contexto["uf"] == "SP"


def test_icms_uf_recente_nao_alerta() -> None:
    r = avaliar_icms_uf(
        uf="SP",
        valid_from_ativa=date(2025, 1, 1),
        hoje=date(2026, 5, 27),
    )
    assert not r.deve_alertar


# ── CBS / IBS ───────────────────────────────────────────────────────────────


def test_cbs_ibs_vigencia_futura_em_60_dias_info() -> None:
    r = avaliar_cbs_ibs(
        valid_from_ativa=date(2026, 1, 1),
        proxima_vigencia_futura=date(2026, 7, 26),  # 60 dias do hoje
        hoje=date(2026, 5, 27),
    )
    assert r.deve_alertar
    assert r.severidade == "info"
    assert r.tipo == TIPO_FUTURA_PROXIMA


def test_cbs_ibs_vigencia_futura_em_120_dias_nao_alerta() -> None:
    r = avaliar_cbs_ibs(
        valid_from_ativa=date(2026, 1, 1),
        proxima_vigencia_futura=date(2026, 9, 24),  # 120 dias
        hoje=date(2026, 5, 27),
    )
    assert not r.deve_alertar


def test_cbs_ibs_sem_vigencia_alguma_eh_critico() -> None:
    r = avaliar_cbs_ibs(
        valid_from_ativa=None,
        proxima_vigencia_futura=None,
        hoje=date(2026, 5, 27),
    )
    assert r.deve_alertar
    assert r.severidade == "critico"
