"""Algoritmo puro de provisão trabalhista mensal.

Decimal-safe. Determinístico. Zero I/O.

Fundamento legal:
  * Férias: CF art. 7º XVII (1/3 constitucional) + CLT art. 129
  * 13º:     CF art. 7º VIII + Lei 4.090/1962
  * INSS patronal: Lei 8.212/1991 art. 22 I (20% sobre folha)
  * FGTS:    Lei 8.036/1990 art. 15 (8%)
  * Simples Nacional/MEI dispensam INSS patronal sobre folha (LC 123/2006
    art. 13): a contribuição está dentro do DAS.

Regras:
  ferias_base = folha_mes / 12
  ferias_total = ferias_base × (1 + 1/3) = ferias_base + 1/3 constitucional
  13_base = folha_mes / 12

  inss_ferias = 0,20 × ferias_total  (se regime aplicável; senão 0)
  inss_13     = 0,20 × 13_base       (idem)
  fgts_ferias = 0,08 × ferias_total
  fgts_13     = 0,08 × 13_base

Quantização: 2 casas, ROUND_HALF_EVEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

ALGORITMO_VERSAO = "prov-2026.05"

_CENTAVO = Decimal("0.01")
_UM_DOZE = Decimal("1") / Decimal("12")
_UM_TERCO = Decimal("1") / Decimal("3")
_ALIQ_INSS_PATRONAL = Decimal("0.2000")
_ALIQ_FGTS = Decimal("0.0800")

# Regimes onde o INSS patronal sobre folha NÃO se aplica.
_REGIMES_SEM_INSS_PATRONAL = frozenset({"mei", "simples_nacional"})


@dataclass(frozen=True, slots=True)
class LinhaProvisao:
    """Uma linha persistida em ``provisao_mensal``."""

    tipo: str
    base_calculo: Decimal
    aliquota: Decimal
    valor_provisao: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoProvisoes:
    """Resultado consolidado — sempre devolve as 6 linhas (INSS/FGTS = 0 se não se aplica)."""

    ferias: LinhaProvisao
    decimo_terceiro: LinhaProvisao
    inss_ferias: LinhaProvisao
    inss_13: LinhaProvisao
    fgts_ferias: LinhaProvisao
    fgts_13: LinhaProvisao
    algoritmo_versao: str = ALGORITMO_VERSAO

    def as_lista(self) -> tuple[LinhaProvisao, ...]:
        return (
            self.ferias,
            self.decimo_terceiro,
            self.inss_ferias,
            self.inss_13,
            self.fgts_ferias,
            self.fgts_13,
        )


def inss_patronal_aplicavel(regime: str) -> bool:
    """SN/MEI não recolhem INSS patronal sobre folha (LC 123/2006 art. 13)."""
    return regime.lower() not in _REGIMES_SEM_INSS_PATRONAL


def calcular_provisoes(folha_mes: Decimal, regime: str) -> ResultadoProvisoes:
    """Calcula as 6 provisões mensais a partir da folha agregada da empresa.

    Args:
        folha_mes: total bruto da folha do mês (Decimal, BRL).
        regime: ``empresa.regime_tributario`` — afeta INSS patronal.

    Returns:
        ResultadoProvisoes com as 6 linhas. Linhas de INSS ficam com
        valor_provisao=0 quando o regime dispensa.
    """
    if folha_mes < Decimal("0"):
        raise ValueError("folha_mes não pode ser negativa")

    ferias_base = _quantizar(folha_mes * _UM_DOZE)
    um_terco_constitucional = _quantizar(ferias_base * _UM_TERCO)
    ferias_total = ferias_base + um_terco_constitucional

    base_13 = _quantizar(folha_mes * _UM_DOZE)

    aliq_inss = _ALIQ_INSS_PATRONAL if inss_patronal_aplicavel(regime) else Decimal("0")
    inss_ferias_val = _quantizar(ferias_total * aliq_inss)
    inss_13_val = _quantizar(base_13 * aliq_inss)

    fgts_ferias_val = _quantizar(ferias_total * _ALIQ_FGTS)
    fgts_13_val = _quantizar(base_13 * _ALIQ_FGTS)

    return ResultadoProvisoes(
        ferias=LinhaProvisao(
            tipo="ferias",
            base_calculo=folha_mes,
            aliquota=_UM_DOZE_PCT_ARREDONDADA,
            valor_provisao=ferias_total,
        ),
        decimo_terceiro=LinhaProvisao(
            tipo="13_salario",
            base_calculo=folha_mes,
            aliquota=_UM_DOZE_PCT_ARREDONDADA,
            valor_provisao=base_13,
        ),
        inss_ferias=LinhaProvisao(
            tipo="inss_ferias",
            base_calculo=ferias_total,
            aliquota=aliq_inss,
            valor_provisao=inss_ferias_val,
        ),
        inss_13=LinhaProvisao(
            tipo="inss_13",
            base_calculo=base_13,
            aliquota=aliq_inss,
            valor_provisao=inss_13_val,
        ),
        fgts_ferias=LinhaProvisao(
            tipo="fgts_ferias",
            base_calculo=ferias_total,
            aliquota=_ALIQ_FGTS,
            valor_provisao=fgts_ferias_val,
        ),
        fgts_13=LinhaProvisao(
            tipo="fgts_13",
            base_calculo=base_13,
            aliquota=_ALIQ_FGTS,
            valor_provisao=fgts_13_val,
        ),
    )


# Aliquota representativa de "1/12" persistida em provisao_mensal.aliquota
# para auditoria — 0.0833 ≈ 8,33%.
_UM_DOZE_PCT_ARREDONDADA = Decimal("0.0833")


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
