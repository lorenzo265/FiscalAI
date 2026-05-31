"""Golden tests do algoritmo puro ``calcula_anomalias`` (Sprint 15 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.advisor.calcula_anomalias import (
    ALGORITMO_VERSAO,
    MetodoDeteccao,
    PontoApuracao,
    SeveridadeAnomalia,
    TipoTributoAnomalia,
    detectar_anomalia,
)


def _serie(valores: list[str], inicio: date = date(2025, 1, 1)) -> list[PontoApuracao]:
    """Constrói série mensal a partir de strings → competências sequenciais."""
    pontos: list[PontoApuracao] = []
    ano, mes = inicio.year, inicio.month
    for v in valores:
        pontos.append(PontoApuracao(competencia=date(ano, mes, 1), valor=Decimal(v)))
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return pontos


# ── Z-score (N ≥ 6) ─────────────────────────────────────────────────────────


def test_zscore_serie_estavel_sem_anomalia() -> None:
    """Histórico de 8 meses ±5% da média; alvo dentro da banda → None."""
    serie = _serie(["1000", "1050", "950", "1020", "980", "1010", "990", "1005"])
    assert detectar_anomalia(TipoTributoAnomalia.PIS, serie) is None


def test_zscore_salto_alta_severidade() -> None:
    """Histórico ~R$1.000; alvo R$3.000 (+200%) → severidade alta."""
    serie = _serie(
        ["1000", "1050", "950", "1020", "980", "1010", "990", "3000"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.ALTA
    assert det.metodo is MetodoDeteccao.ZSCORE
    assert det.competencia == date(2025, 8, 1)
    assert det.valor_observado == Decimal("3000.00")
    assert det.z_score > Decimal("3.0")
    assert det.delta_percentual > Decimal("1.9")
    assert det.amostra_n == 7
    assert det.algoritmo_versao == ALGORITMO_VERSAO


def test_zscore_queda_severa() -> None:
    """Histórico ~R$5.000; alvo R$500 (-90%) → alta com z negativo."""
    serie = _serie(
        ["5000", "5100", "4900", "5050", "4950", "5000", "5025", "500"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.COFINS, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.ALTA
    assert det.z_score < Decimal("-3.0")
    assert det.delta_percentual < Decimal("-0.85")


def test_zscore_severidade_media() -> None:
    """Alvo a ~2 desvios da média → media (não alta)."""
    # Histórico ~R$ 1.000, desvio ~67; alvo 1170 → z ≈ 2,5 → media.
    serie = _serie(
        ["1000", "1100", "900", "1050", "950", "1025", "975", "1170"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.ICMS, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.MEDIA
    assert det.metodo is MetodoDeteccao.ZSCORE
    assert Decimal("2.0") <= abs(det.z_score) < Decimal("3.0")


def test_zscore_severidade_baixa_no_limite() -> None:
    """Alvo a ~1,7 desvios → severidade baixa."""
    serie = _serie(
        ["1000", "1100", "900", "1050", "950", "1025", "975", "1115"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.IRPJ, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.BAIXA
    assert Decimal("1.5") <= abs(det.z_score) < Decimal("2.0")


def test_zscore_serie_constante_alvo_igual_sem_anomalia() -> None:
    """8 meses todos R$ 500; alvo R$ 500 → None (desvio = 0, sem mudança)."""
    serie = _serie(["500"] * 8)
    assert detectar_anomalia(TipoTributoAnomalia.ISS, serie) is None


def test_zscore_serie_constante_alvo_diferente_emite_anomalia() -> None:
    """7 zeros + alvo R$ 5.000 → alta sintética (saiu do zero)."""
    serie = _serie(["0"] * 7 + ["5000"])
    det = detectar_anomalia(TipoTributoAnomalia.DAS, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.ALTA
    assert det.valor_esperado == Decimal("0.00")
    assert det.valor_observado == Decimal("5000.00")
    # Esperado = 0 ⇒ delta capada
    assert det.delta_percentual == Decimal("999.9999")


def test_zscore_amostra_grande_13_meses() -> None:
    """Série de 13 pontos com sazonalidade; alvo no padrão → None."""
    serie = _serie(
        ["1000", "1100", "1200", "1100", "1000", "900",
         "850", "900", "1000", "1100", "1200", "1300", "1100"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.ICMS, serie)
    # Esperamos que o último (1100) esteja dentro da banda do histórico.
    assert det is None or det.severidade is SeveridadeAnomalia.BAIXA


# ── IQR (3 ≤ N < 6) ─────────────────────────────────────────────────────────


def test_iqr_serie_curta_sem_anomalia() -> None:
    """4 pontos próximos; alvo dentro do IQR → None."""
    serie = _serie(["1000", "1050", "950", "1020"])
    assert detectar_anomalia(TipoTributoAnomalia.PIS, serie) is None


def test_iqr_outlier_alta_severidade() -> None:
    """3 pontos ~R$1.000; alvo R$5.000 → alta via IQR."""
    serie = _serie(["1000", "1050", "950", "5000"])
    det = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert det is not None
    assert det.metodo is MetodoDeteccao.IQR
    assert det.severidade is SeveridadeAnomalia.ALTA
    assert det.amostra_n == 3


def test_iqr_outlier_media_severidade() -> None:
    """3 pontos [900, 1000, 1100] → Q1=950, Q3=1050, IQR=100.
    Alvo 1250 está em (Q3+1.5*IQR=1200, Q3+3*IQR=1350) → media.
    """
    serie = _serie(["1000", "1100", "900", "1250"])
    det = detectar_anomalia(TipoTributoAnomalia.COFINS, serie)
    assert det is not None
    assert det.metodo is MetodoDeteccao.IQR
    assert det.severidade is SeveridadeAnomalia.MEDIA


def test_iqr_serie_5_pontos_constantes_alvo_zerou() -> None:
    """5 meses constantes em R$ 1.000; alvo zerou → alta sintética."""
    serie = _serie(["1000"] * 4 + ["0"])
    det = detectar_anomalia(TipoTributoAnomalia.IRPJ, serie)
    assert det is not None
    assert det.severidade is SeveridadeAnomalia.ALTA


# ── Borda mínima e validações ───────────────────────────────────────────────


def test_historico_insuficiente_2_pontos() -> None:
    """Apenas 2 pontos (1 histórico + 1 alvo) → None silencioso."""
    serie = _serie(["1000", "5000"])
    assert detectar_anomalia(TipoTributoAnomalia.PIS, serie) is None


def test_historico_insuficiente_1_ponto() -> None:
    """Único ponto (alvo, sem histórico) → None."""
    serie = _serie(["1000"])
    assert detectar_anomalia(TipoTributoAnomalia.PIS, serie) is None


def test_serie_vazia_levanta_valueerror() -> None:
    with pytest.raises(ValueError, match="vazia"):
        detectar_anomalia(TipoTributoAnomalia.PIS, [])


def test_valor_negativo_levanta_valueerror() -> None:
    serie = _serie(["1000", "1100", "1050"])
    serie.append(PontoApuracao(competencia=date(2025, 4, 1), valor=Decimal("-10")))
    with pytest.raises(ValueError, match="negativ"):
        detectar_anomalia(TipoTributoAnomalia.PIS, serie)


# ── Mensagem e quantização ──────────────────────────────────────────────────


def test_mensagem_contem_tipo_e_percentual() -> None:
    serie = _serie(
        ["1000", "1050", "950", "1020", "980", "1010", "990", "3000"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert det is not None
    assert "PIS" in det.mensagem
    assert "subiu" in det.mensagem
    assert "%" in det.mensagem
    assert "R$" in det.mensagem


def test_valores_quantizados_em_centavos() -> None:
    serie = _serie(
        ["1000.5555", "1050", "950", "1020", "980", "1010", "990", "3000.123"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert det is not None
    assert det.valor_observado == Decimal("3000.12")
    # valor_esperado em 2 casas
    assert det.valor_esperado.as_tuple().exponent == -2


def test_z_score_quantizado_3_casas() -> None:
    serie = _serie(
        ["1000", "1050", "950", "1020", "980", "1010", "990", "3000"]
    )
    det = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert det is not None
    assert det.z_score.as_tuple().exponent == -3


def test_algoritmo_versao_e_estavel() -> None:
    """Bump consciente: alterar essa string exige nova migration/changelog."""
    assert ALGORITMO_VERSAO == "advisor.anomalia.v1"


def test_determinismo_mesma_entrada_mesma_saida() -> None:
    """Princípio §8.4 — função pura, mesma entrada produz mesma saída."""
    serie = _serie(
        ["1000", "1050", "950", "1020", "980", "1010", "990", "2500"]
    )
    a = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    b = detectar_anomalia(TipoTributoAnomalia.PIS, serie)
    assert a == b


def test_tipos_disponiveis_cobrem_check_do_db() -> None:
    """Espelha CHECK constraint ck_anomalia_tipo da migration 0036."""
    tipos = {t.value for t in TipoTributoAnomalia}
    assert tipos == {"das", "irpj", "csll", "pis", "cofins", "iss", "icms"}
