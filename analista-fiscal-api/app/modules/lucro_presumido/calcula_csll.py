"""Calculadora CSLL trimestral — Lucro Presumido.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 20 — percentuais de presunção CSLL: 12% (regra
    geral) ou 32% (serviços profissionais e intermediação).
  * Lei 7.689/1988 art. 3º + Lei 9.430/1996 art. 28 — alíquota 9%.
  * Lei 9.430/1996 art. 28 — apuração trimestral.
  * IN RFB 1.700/2017 art. 34.
  * Lei 9.430/1996 art. 64 (c/c IN RFB 1.234/2012) — CSLL retida na fonte
    (PCC 4,65%: 1% CSLL + 3% Cofins + 0,65% PIS, em pagamentos PJ→PJ por
    serviços listados no art. 30 da Lei 10.833/2003) deduzida da CSLL devida
    no trimestre.

Diferenças vs. IRPJ:
  * Sem adicional (CSLL é alíquota única 9%).
  * Percentual de presunção diferente do IRPJ — vem da MESMA tabela SCD
    ``presuncao_lucro_presumido``, coluna ``percentual_csll``.

Fórmula (v2 — FA3/M3):

  base_presumida    = receita_bruta_trimestre × percentual_csll_atividade
  base_total        = base_presumida + ganhos_capital + receitas_aplicacoes
                    + outras_adicoes
  csll_devida       = base_total × 9%
  csll_consumida    = min(csll_a_compensar, csll_devida)
  csll_a_recolher   = csll_devida − csll_consumida  (nunca negativo)
  csll_saldo_credor = csll_a_compensar − csll_consumida  (para próx. trimestre)

Quantização: ``ROUND_HALF_EVEN`` 2 casas aplicada uma única vez ao
``csll_devida`` antes da subtração (espelha padrão do IRPJ v2).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "lp.csll.trimestral.v2"

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
    csll: Decimal                   # CSLL bruta antes da dedução (= csll_devida)
    csll_a_compensar: Decimal       # CSLL retida na fonte informada como input
    csll_consumida: Decimal         # parte efetivamente abatida nesse trimestre
    csll_saldo_credor: Decimal      # excedente para o próximo trimestre
    csll_a_recolher: Decimal        # valor final a recolher (= csll − csll_consumida)
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
    csll_a_compensar: Decimal = _ZERO,
) -> ResultadoCsllLp:
    """Calcula CSLL do trimestre com dedução de CSLL retida na fonte.

    Args:
        receita_bruta_trimestre: receita do trimestre (BRL).
        percentual_presuncao: vem de ``presuncao_lucro_presumido.percentual_csll``.
        ganhos_capital: somado integral à base.
        receitas_aplicacoes: somadas integrais.
        outras_adicoes: ajustes/recuperações integrais.
        csll_a_compensar: CSLL retida na fonte no trimestre (Lei 9.430 art. 64
            c/c Lei 10.833/2003 art. 30 — retenção PCC 1% de CSLL em serviços
            PJ→PJ). Aceita também saldo credor de CSLL acumulado de trimestres
            anteriores. Não pode ser negativo. Default zero (backward-compatible).

    Returns:
        ResultadoCsllLp com ``csll_a_recolher`` (a recolher) +
        ``csll_saldo_credor`` (excedente para próximo trimestre).

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
    if csll_a_compensar < _ZERO:
        raise ValueError(
            f"csll_a_compensar não pode ser negativo: {csll_a_compensar}"
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

    # ── Quantização única no fim (espelha padrão IRPJ v2) ────────────────
    csll_devida = _quantizar(base_total * _ALIQ_CSLL)

    # ── CSLL retida a compensar (FA3/M3) ─────────────────────────────────
    # Lei 9.430/1996 art. 64 c/c Lei 10.833/2003 art. 30: CSLL retida na
    # fonte (1% do PCC de 4,65%) é deduzida da CSLL devida no trimestre.
    csll_a_compensar_q = _quantizar(csll_a_compensar)
    csll_consumida = min(csll_a_compensar_q, csll_devida)
    csll_saldo_credor = csll_a_compensar_q - csll_consumida
    csll_a_recolher = csll_devida - csll_consumida

    return ResultadoCsllLp(
        receita_bruta_trimestre=receita_bruta_trimestre,
        percentual_presuncao=percentual_presuncao,
        base_presumida=_quantizar(base_presumida),
        ganhos_capital=ganhos_capital,
        receitas_aplicacoes=receitas_aplicacoes,
        outras_adicoes=outras_adicoes,
        base_total=_quantizar(base_total),
        aliquota=_ALIQ_CSLL,
        csll=csll_devida,
        csll_a_compensar=csll_a_compensar_q,
        csll_consumida=csll_consumida,
        csll_saldo_credor=csll_saldo_credor,
        csll_a_recolher=csll_a_recolher,
    )
