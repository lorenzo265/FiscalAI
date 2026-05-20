"""Calculadoras PIS e Cofins — regime cumulativo mensal (Lucro Presumido).

Camada 1 (determinística). Funções puras, zero I/O.

Fundamento legal:
  * Lei 9.715/1998 — PIS cumulativo, alíquota 0,65%.
  * Lei 9.718/1998 — Cofins cumulativo, alíquota 3%.
  * Lei 9.718/1998 art. 3º §2º — exclusões da base:
      I — vendas canceladas e descontos incondicionais concedidos;
      II — reversões de provisões e recuperações de créditos baixados;
      III — receitas de exportação não tributadas;
      IV — IPI destacado nas notas (quando empresa é contribuinte do IPI);
      V — ICMS-ST quando o vendedor é substituto tributário.

Fórmula (idêntica para PIS e Cofins, só muda alíquota):

  base = receita_bruta_mes − exclusoes_legais
  tributo = base × aliquota
  (0,65% PIS / 3% Cofins)

Apuração mensal — recolhimento via DARF até o 25º dia útil do mês seguinte
ao da apuração (Lei 11.933/2009).

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO_PIS = "lp.pis.cumulativo.v1"
ALGORITMO_VERSAO_COFINS = "lp.cofins.cumulativo.v1"

_CENTAVO = Decimal("0.01")
_ALIQ_PIS = Decimal("0.0065")
_ALIQ_COFINS = Decimal("0.0300")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoTributoCumulativo:
    """Snapshot persistido em ``apuracao_fiscal``."""

    receita_bruta_mes: Decimal
    exclusoes: Decimal
    base_calculo: Decimal
    aliquota: Decimal
    tributo: Decimal
    algoritmo_versao: str


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _calcular_cumulativo(
    receita_bruta_mes: Decimal,
    exclusoes: Decimal,
    aliquota: Decimal,
    algoritmo_versao: str,
) -> ResultadoTributoCumulativo:
    if receita_bruta_mes < _ZERO:
        raise ValueError(
            f"receita_bruta_mes não pode ser negativa: {receita_bruta_mes}"
        )
    if exclusoes < _ZERO:
        raise ValueError(f"exclusoes não pode ser negativa: {exclusoes}")
    if exclusoes > receita_bruta_mes:
        raise ValueError(
            f"exclusoes ({exclusoes}) não pode exceder a receita "
            f"({receita_bruta_mes})"
        )

    base = receita_bruta_mes - exclusoes
    tributo = _quantizar(base * aliquota)

    return ResultadoTributoCumulativo(
        receita_bruta_mes=receita_bruta_mes,
        exclusoes=exclusoes,
        base_calculo=_quantizar(base),
        aliquota=aliquota,
        tributo=tributo,
        algoritmo_versao=algoritmo_versao,
    )


def calcular_pis_cumulativo_mensal(
    receita_bruta_mes: Decimal,
    *,
    exclusoes: Decimal = _ZERO,
) -> ResultadoTributoCumulativo:
    """PIS cumulativo — 0,65% sobre receita bruta menos exclusões legais."""
    return _calcular_cumulativo(
        receita_bruta_mes, exclusoes, _ALIQ_PIS, ALGORITMO_VERSAO_PIS
    )


def calcular_cofins_cumulativo_mensal(
    receita_bruta_mes: Decimal,
    *,
    exclusoes: Decimal = _ZERO,
) -> ResultadoTributoCumulativo:
    """Cofins cumulativo — 3,0% sobre receita bruta menos exclusões legais."""
    return _calcular_cumulativo(
        receita_bruta_mes, exclusoes, _ALIQ_COFINS, ALGORITMO_VERSAO_COFINS
    )
