"""Calculadora CSLL trimestral — Lucro Presumido.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 20 — percentuais de presunção CSLL: 12% (regra
    geral) ou 32% (serviços profissionais e intermediação).
  * Lei 7.689/1988 art. 3º + Lei 9.430/1996 art. 28 — alíquota 9%.
  * Lei 9.430/1996 art. 28 — apuração trimestral.
  * IN RFB 1.700/2017 art. 34.

Diferenças vs. IRPJ:
  * Sem adicional (CSLL é alíquota única 9%).
  * Percentual de presunção diferente do IRPJ — vem da MESMA tabela SCD
    ``presuncao_lucro_presumido``, coluna ``percentual_csll``.

Fórmula:

  base_presumida = receita_bruta_trimestre × percentual_csll_atividade
  base_total     = base_presumida
                 + ganhos_capital
                 + receitas_aplicacoes
                 + outras_adicoes
  csll           = base_total × 9%

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "lp.csll.trimestral.v1"

_CENTAVO = Decimal("0.01")
_ALIQ_CSLL = Decimal("0.0900")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoCsllLp:
    """Snapshot persistido em ``apuracao_fiscal`` (tipo='csll')."""

    receita_bruta_trimestre: Decimal
    percentual_presuncao: Decimal
    base_presumida: Decimal
    ganhos_capital: Decimal
    receitas_aplicacoes: Decimal
    outras_adicoes: Decimal
    base_total: Decimal
    aliquota: Decimal
    csll: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_csll_trimestral(
    receita_bruta_trimestre: Decimal,
    percentual_presuncao: Decimal,
    *,
    ganhos_capital: Decimal = _ZERO,
    receitas_aplicacoes: Decimal = _ZERO,
    outras_adicoes: Decimal = _ZERO,
) -> ResultadoCsllLp:
    """Calcula CSLL do trimestre.

    Args:
        receita_bruta_trimestre: receita do trimestre (BRL).
        percentual_presuncao: vem de ``presuncao_lucro_presumido.percentual_csll``.
        ganhos_capital: somado integral à base.
        receitas_aplicacoes: somadas integrais.
        outras_adicoes: ajustes/recuperações integrais.

    Returns:
        ResultadoCsllLp.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if receita_bruta_trimestre < _ZERO:
        raise ValueError(
            f"receita_bruta_trimestre não pode ser negativa: "
            f"{receita_bruta_trimestre}"
        )
    if percentual_presuncao < _ZERO or percentual_presuncao > Decimal("1"):
        raise ValueError(
            f"percentual_presuncao fora de [0, 1]: {percentual_presuncao}"
        )
    for nome, v in (
        ("ganhos_capital", ganhos_capital),
        ("receitas_aplicacoes", receitas_aplicacoes),
        ("outras_adicoes", outras_adicoes),
    ):
        if v < _ZERO:
            raise ValueError(f"{nome} não pode ser negativo: {v}")

    base_presumida = receita_bruta_trimestre * percentual_presuncao
    base_total = (
        base_presumida + ganhos_capital + receitas_aplicacoes + outras_adicoes
    )
    csll = _quantizar(base_total * _ALIQ_CSLL)

    return ResultadoCsllLp(
        receita_bruta_trimestre=receita_bruta_trimestre,
        percentual_presuncao=percentual_presuncao,
        base_presumida=_quantizar(base_presumida),
        ganhos_capital=ganhos_capital,
        receitas_aplicacoes=receitas_aplicacoes,
        outras_adicoes=outras_adicoes,
        base_total=_quantizar(base_total),
        aliquota=_ALIQ_CSLL,
        csll=csll,
    )
