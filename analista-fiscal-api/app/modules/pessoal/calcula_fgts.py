"""Cálculo do FGTS do empregador.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 8.036/1990 art. 15 — 8% sobre remuneração do empregado CLT.
  * LC 150/2015 art. 34 — 8% empregado doméstico.
  * Lei 10.097/2000 + Decreto 5.598/2005 — 2% jovem aprendiz.

FGTS não é descontado do empregado — é encargo do empregador. Por isso não
afeta ``valor_liquido`` do holerite, mas vai para ``total_fgts_empregador``
da folha (e mais tarde gera lançamento contábil em ``2.1.3.02 FGTS a
Recolher`` — integração com o motor contábil planejada na Sprint 11).

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "fgts.empregador.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoFgts:
    """Snapshot do cálculo persistido no holerite."""

    salario_bruto: Decimal
    aliquota: Decimal
    fgts: Decimal
    vinculo: str
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_fgts(
    salario_bruto: Decimal,
    aliquota: Decimal,
    *,
    vinculo: str = "clt",
) -> ResultadoFgts:
    """Calcula o FGTS do empregador (encargo, não desconto).

    Args:
        salario_bruto: remuneração do empregado no mês.
        aliquota: alíquota vigente vinda de ``tabela_fgts_aliquota``
                  (0,0800 CLT/doméstico, 0,0200 jovem aprendiz).
        vinculo: persistido no resultado para auditoria.

    Returns:
        ResultadoFgts.

    Raises:
        ValueError: se ``salario_bruto`` ou ``aliquota`` negativos.
    """
    if salario_bruto < _ZERO:
        raise ValueError(f"salario_bruto não pode ser negativo: {salario_bruto}")
    if aliquota < _ZERO:
        raise ValueError(f"aliquota não pode ser negativa: {aliquota}")

    fgts = (salario_bruto * aliquota).quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    return ResultadoFgts(
        salario_bruto=salario_bruto,
        aliquota=aliquota,
        fgts=fgts,
        vinculo=vinculo,
    )
