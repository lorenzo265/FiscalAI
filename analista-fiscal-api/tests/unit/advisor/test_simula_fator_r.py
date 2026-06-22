"""Golden tests do simulador Fator R — Anexo III vs Anexo V (Sprint 15 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.advisor.simula_fator_r import (
    ALGORITMO_VERSAO,
    simular_fator_r,
)
from app.modules.fiscal.calcula_das import FaixaDAS
from app.shared.exceptions import SemDadosParaSugestao

# ── Tabelas vigentes (LC 123/2006 anexo III e V — Resolução CGSN 140/2018) ──


def _faixas_anexo_iii() -> list[FaixaDAS]:
    """Anexo III (serviços/locação de bens móveis)."""
    return [
        FaixaDAS(1, Decimal("180000"), Decimal("0.0600"), Decimal("0")),
        FaixaDAS(2, Decimal("360000"), Decimal("0.1120"), Decimal("9360")),
        FaixaDAS(3, Decimal("720000"), Decimal("0.1350"), Decimal("17640")),
        FaixaDAS(4, Decimal("1800000"), Decimal("0.1600"), Decimal("35640")),
        FaixaDAS(5, Decimal("3600000"), Decimal("0.2100"), Decimal("125640")),
        FaixaDAS(6, Decimal("4800000"), Decimal("0.3300"), Decimal("648000")),
    ]


def _faixas_anexo_v() -> list[FaixaDAS]:
    """Anexo V (atividades intelectuais com Fator R < 28%)."""
    return [
        FaixaDAS(1, Decimal("180000"), Decimal("0.1550"), Decimal("0")),
        FaixaDAS(2, Decimal("360000"), Decimal("0.1800"), Decimal("4500")),
        FaixaDAS(3, Decimal("720000"), Decimal("0.1950"), Decimal("9900")),
        FaixaDAS(4, Decimal("1800000"), Decimal("0.2050"), Decimal("17100")),
        FaixaDAS(5, Decimal("3600000"), Decimal("0.2300"), Decimal("62100")),
        FaixaDAS(6, Decimal("4800000"), Decimal("0.3050"), Decimal("540000")),
    ]


_COMP = date(2026, 5, 1)


# ── Fator R aplicado (boundary tests) ───────────────────────────────────────


def test_fator_r_exatamente_28pct_resolve_anexo_iii() -> None:
    """28,00% exato → Anexo III (regra ``>=`` da norma)."""
    sim = simular_fator_r(
        folha_12m=Decimal("280000"),
        receita_12m=Decimal("1000000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.fator_r_atual == Decimal("0.2800")
    assert sim.anexo_atual_efetivo == "III"


def test_fator_r_2799_resolve_anexo_v() -> None:
    """27,99% → Anexo V (abaixo do limiar)."""
    sim = simular_fator_r(
        folha_12m=Decimal("279900"),
        receita_12m=Decimal("1000000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.anexo_atual_efetivo == "V"


def test_fator_r_2801_resolve_anexo_iii() -> None:
    """28,01% → Anexo III."""
    sim = simular_fator_r(
        folha_12m=Decimal("280100"),
        receita_12m=Decimal("1000000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.anexo_atual_efetivo == "III"


# ── Economia anual estimada ─────────────────────────────────────────────────


def test_anexo_iii_e_mais_barato_que_anexo_v_em_faixa_3() -> None:
    """Faixa 3 (RBT12 R$ 720k): III sempre vence — economia positiva relevante."""
    sim = simular_fator_r(
        folha_12m=Decimal("100000"),  # Fator R 14% — está no V
        receita_12m=Decimal("720000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.das_anexo_iii_mensal < sim.das_anexo_v_mensal
    assert sim.economia_anual_estimada > Decimal("0")
    assert sim.anexo_recomendado == "III"
    assert sim.deve_migrar is True


def test_gap_folha_para_migracao_e_calculado() -> None:
    """Empresa com Fator R 14% precisa dobrar a folha (14%→28%)."""
    sim = simular_fator_r(
        folha_12m=Decimal("100000"),
        receita_12m=Decimal("720000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    # 28% × 720k = 201_600. Falta 101_600 anual.
    assert sim.folha_necessaria_28pct == Decimal("201600.00")
    assert sim.gap_folha_anual == Decimal("101600.00")


def test_gap_folha_zero_quando_ja_acima_de_28pct() -> None:
    """Empresa já no Anexo III (Fator R 35%) — gap = 0."""
    sim = simular_fator_r(
        folha_12m=Decimal("350000"),
        receita_12m=Decimal("1000000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.gap_folha_anual == Decimal("0")
    assert sim.anexo_atual_efetivo == "III"
    assert sim.deve_migrar is False  # já está no recomendado


def test_receita_mes_referencia_e_a_media_anual() -> None:
    """receita_mes_referencia = receita_12m / 12, quantizada."""
    sim = simular_fator_r(
        folha_12m=Decimal("100000"),
        receita_12m=Decimal("1200000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.receita_mes_referencia == Decimal("100000.00")


# ── Edge cases ──────────────────────────────────────────────────────────────


def test_receita_zero_levanta_sem_dados() -> None:
    with pytest.raises(SemDadosParaSugestao):
        simular_fator_r(
            folha_12m=Decimal("50000"),
            receita_12m=Decimal("0"),
            competencia=_COMP,
            faixas_anexo_iii=_faixas_anexo_iii(),
            faixas_anexo_v=_faixas_anexo_v(),
        )


def test_folha_zero_resolve_para_anexo_v() -> None:
    """Empresa sem folha (Fator R = 0%) → Anexo V."""
    sim = simular_fator_r(
        folha_12m=Decimal("0"),
        receita_12m=Decimal("500000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert sim.fator_r_atual == Decimal("0")
    assert sim.anexo_atual_efetivo == "V"


def test_folha_negativa_levanta_valueerror() -> None:
    with pytest.raises(ValueError, match="negativ"):
        simular_fator_r(
            folha_12m=Decimal("-10"),
            receita_12m=Decimal("100000"),
            competencia=_COMP,
            faixas_anexo_iii=_faixas_anexo_iii(),
            faixas_anexo_v=_faixas_anexo_v(),
        )


def test_faixas_vazias_levanta_valueerror() -> None:
    with pytest.raises(ValueError, match="não podem ser vazias"):
        simular_fator_r(
            folha_12m=Decimal("100000"),
            receita_12m=Decimal("500000"),
            competencia=_COMP,
            faixas_anexo_iii=[],
            faixas_anexo_v=_faixas_anexo_v(),
        )


# ── Metadados ───────────────────────────────────────────────────────────────


def test_algoritmo_versao_estavel() -> None:
    """Bump consciente: alterar essa string exige changelog + nova migration de auditoria."""
    assert ALGORITMO_VERSAO == "advisor.fator-r.v1"


def test_observacao_estimativa_cita_norma() -> None:
    sim = simular_fator_r(
        folha_12m=Decimal("280000"),
        receita_12m=Decimal("1000000"),
        competencia=_COMP,
        faixas_anexo_iii=_faixas_anexo_iii(),
        faixas_anexo_v=_faixas_anexo_v(),
    )
    assert "LC 123" in sim.fonte_norma
    assert "CGSN" in sim.observacao_estimativa
    assert "estimativa" in sim.observacao_estimativa.lower()


def test_determinismo_mesma_entrada_mesma_saida() -> None:
    """Princípio §8.4 — função pura."""
    args: dict[str, object] = {
        "folha_12m": Decimal("250000"),
        "receita_12m": Decimal("900000"),
        "competencia": _COMP,
        "faixas_anexo_iii": _faixas_anexo_iii(),
        "faixas_anexo_v": _faixas_anexo_v(),
    }
    a = simular_fator_r(**args)  # type: ignore[arg-type]
    b = simular_fator_r(**args)  # type: ignore[arg-type]
    assert a == b
