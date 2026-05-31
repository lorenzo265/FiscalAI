"""Testes do orquestrador puro ``sugestoes_otimizacao`` (Sprint 15 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.advisor.simula_fator_r import SimulacaoFatorR
from app.modules.advisor.sugestoes_otimizacao import (
    ApuracaoPendente,
    InsumosSugestoes,
    calcular_sugestoes,
    sugerir_migracao_fator_r,
    sugerir_parcelamento_atrasado,
)


_COMP = date(2026, 5, 15)


def _simulacao(
    *,
    fator_atual: str,
    deve_migrar: bool,
    anexo_atual: str,
    anexo_recomendado: str,
    economia_anual: str,
    gap_folha: str = "0",
) -> SimulacaoFatorR:
    return SimulacaoFatorR(
        fator_r_atual=Decimal(fator_atual),
        fator_r_limiar=Decimal("0.28"),
        folha_12m=Decimal("100000.00"),
        receita_12m=Decimal("720000.00"),
        folha_necessaria_28pct=Decimal("201600.00"),
        gap_folha_anual=Decimal(gap_folha),
        receita_mes_referencia=Decimal("60000.00"),
        das_anexo_iii_mensal=Decimal("4500.00"),
        das_anexo_v_mensal=Decimal("9750.00"),
        economia_mensal=Decimal("0.00"),
        economia_anual_estimada=Decimal(economia_anual),
        anexo_atual_efetivo=anexo_atual,
        anexo_recomendado=anexo_recomendado,
        deve_migrar=deve_migrar,
        competencia_referencia=_COMP,
    )


def _pendente(competencia: date, valor: str = "1000") -> ApuracaoPendente:
    return ApuracaoPendente(
        apuracao_id="00000000-0000-0000-0000-000000000000",
        tipo="das",
        competencia=competencia,
        valor=Decimal(valor),
        vencimento=date(
            competencia.year + (1 if competencia.month == 12 else 0),
            (competencia.month % 12) + 1,
            20,
        ),
        status="calculado",
    )


# ── Fator R ──────────────────────────────────────────────────────────────────


def test_fator_r_sugere_migrar_para_anexo_iii() -> None:
    sim = _simulacao(
        fator_atual="0.1500",
        deve_migrar=True,
        anexo_atual="V",
        anexo_recomendado="III",
        economia_anual="62000.00",
        gap_folha="101600.00",
    )
    sug = sugerir_migracao_fator_r(sim)
    assert sug is not None
    assert sug.codigo == "fator_r_migrar_anexo_iii"
    assert sug.severidade == "alta"  # > R$ 1.000
    assert "28%" in sug.descricao
    assert sug.economia_anual_estimada == Decimal("62000.00")


def test_fator_r_severidade_media_para_economia_modesta() -> None:
    sim = _simulacao(
        fator_atual="0.2700",
        deve_migrar=True,
        anexo_atual="V",
        anexo_recomendado="III",
        economia_anual="500.00",
    )
    sug = sugerir_migracao_fator_r(sim)
    assert sug is not None
    assert sug.severidade == "media"


def test_fator_r_sem_simulacao_nao_sugere() -> None:
    assert sugerir_migracao_fator_r(None) is None


def test_fator_r_quando_ja_no_anexo_recomendado_nao_sugere() -> None:
    sim = _simulacao(
        fator_atual="0.3500",
        deve_migrar=False,
        anexo_atual="III",
        anexo_recomendado="III",
        economia_anual="0",
    )
    assert sugerir_migracao_fator_r(sim) is None


def test_fator_r_filtro_economia_minima() -> None:
    """Economia menor que R$ 100/ano é filtrada como ruído."""
    sim = _simulacao(
        fator_atual="0.2790",
        deve_migrar=True,
        anexo_atual="V",
        anexo_recomendado="III",
        economia_anual="50.00",
    )
    assert sugerir_migracao_fator_r(sim) is None


def test_fator_r_sugestao_inversa_anexo_v_e_informativa() -> None:
    """Quando V vence III, sugestão é só informativa (impactos trabalhistas)."""
    sim = _simulacao(
        fator_atual="0.3200",
        deve_migrar=True,
        anexo_atual="III",
        anexo_recomendado="V",
        economia_anual="2000.00",
    )
    sug = sugerir_migracao_fator_r(sim)
    assert sug is not None
    assert sug.codigo == "fator_r_migrar_anexo_v"
    assert sug.severidade == "informativa"


# ── Parcelamento DAS atrasado ───────────────────────────────────────────────


def test_parcelamento_quando_ha_atrasados() -> None:
    pendentes = [
        _pendente(date(2026, 1, 1), "1500"),
        _pendente(date(2026, 2, 1), "1600"),
    ]
    sug = sugerir_parcelamento_atrasado(pendentes, hoje=_COMP)
    assert sug is not None
    assert sug.codigo == "parcelar_das_atrasado"
    assert sug.severidade == "alta"
    assert sug.economia_anual_estimada is None  # não é monetária
    assert "Lei 10.522" in sug.fonte_norma
    assert sug.detalhes["quantidade_atrasadas"] == "2"


def test_parcelamento_sem_atrasados_devolve_none() -> None:
    """Apuração da competência corrente — vencimento futuro."""
    pendentes = [_pendente(date(2026, 4, 1), "1000")]
    # Vencimento DAS abril/26 = 20/maio/26; "hoje" = 15/maio/26 → ainda não venceu.
    assert sugerir_parcelamento_atrasado(pendentes, hoje=_COMP) is None


def test_parcelamento_apenas_das_e_considerado() -> None:
    """Sugestão é específica para DAS — outros tributos pendentes não contam."""
    pendentes = [
        ApuracaoPendente(
            apuracao_id="x",
            tipo="irpj",
            competencia=date(2025, 12, 1),
            valor=Decimal("5000"),
            vencimento=date(2026, 1, 20),
            status="calculado",
        )
    ]
    assert sugerir_parcelamento_atrasado(pendentes, hoje=_COMP) is None


# ── Orquestrador ────────────────────────────────────────────────────────────


def test_calcular_sugestoes_combina_heuristicas_e_ordena() -> None:
    sim = _simulacao(
        fator_atual="0.1500",
        deve_migrar=True,
        anexo_atual="V",
        anexo_recomendado="III",
        economia_anual="60000.00",
    )
    pendentes = [_pendente(date(2026, 1, 1), "2000")]
    insumos = InsumosSugestoes(
        simulacao_fator_r=sim,
        apuracoes_pendentes=pendentes,
        competencia_referencia=_COMP,
    )
    sugestoes = calcular_sugestoes(insumos)
    assert len(sugestoes) == 2
    # Ambas alta — ordenam alfabéticamente pelo código.
    assert all(s.severidade == "alta" for s in sugestoes)
    codigos = [s.codigo for s in sugestoes]
    assert codigos == sorted(codigos)


def test_calcular_sugestoes_filtra_nulls() -> None:
    insumos = InsumosSugestoes(
        simulacao_fator_r=None,
        apuracoes_pendentes=[],
        competencia_referencia=_COMP,
    )
    assert calcular_sugestoes(insumos) == []


def test_calcular_sugestoes_ordem_severidade_alta_primeiro() -> None:
    sim_informativa = _simulacao(
        fator_atual="0.3200",
        deve_migrar=True,
        anexo_atual="III",
        anexo_recomendado="V",
        economia_anual="2000.00",
    )
    pendentes = [_pendente(date(2026, 1, 1), "5000")]
    insumos = InsumosSugestoes(
        simulacao_fator_r=sim_informativa,
        apuracoes_pendentes=pendentes,
        competencia_referencia=_COMP,
    )
    sugestoes = calcular_sugestoes(insumos)
    # Parcelamento (alta) vem antes da migração inversa (informativa).
    assert sugestoes[0].codigo == "parcelar_das_atrasado"
    assert sugestoes[0].severidade == "alta"
    assert sugestoes[1].severidade == "informativa"
