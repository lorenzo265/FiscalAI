"""Cálculo do pró-labore mensal — sócio (contribuinte individual).

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 8.212/1991 art. 21 — alíquota INSS contribuinte individual: 20%
    sobre salário-de-contribuição, ou 11% sobre o pró-labore quando o sócio
    presta serviço a empresa optante (plano simplificado, Lei 9.876/1999
    art. 4º; consolidado na IN RFB 971/2009 art. 65 II `a`).
  * Lei 14.848/2024 — tabela mensal IRRF (mesma usada no holerite CLT).
  * Portaria Interministerial MPS/MF — teto previdenciário anual (vem da
    SCD ``tabela_inss_faixa`` com ``tipo='contribuinte_individual'``).

Diferença em relação ao INSS empregado (escalonado):
  * Pró-labore usa alíquota PLANA (11%) sobre a base limitada ao teto.
  * Não há FGTS — sócio não é segurado FGTS.

Fórmula:

  base_inss     = min(bruto, teto_previdenciario)
  inss          = base_inss × aliquota_inss        (default 11%)
  base_irrf     = bruto − inss − (dependentes × deducao_por_dependente)
                  [deducao_por_dependente vem da SCD FaixaIrrf.deducao_dependente
                   — nunca hardcoded; o valor vigente é carregado pelo service
                   ao consultar a tabela IRRF do período]
  irrf          = max(0, base_irrf × aliquota_faixa − parcela_deduzir_faixa)
  valor_liquido = bruto − inss − irrf

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.modules.pessoal.calcula_irrf import (
    FaixaIrrf,
    ResultadoIrrf,
    calcular_irrf_mensal,
)

getcontext().prec = 28

ALGORITMO_VERSAO = "prolabore.v1"

_CENTAVO = Decimal("0.01")
_ALIQ_DEFAULT = Decimal("0.1100")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoProlabore:
    """Snapshot do cálculo persistido em ``prolabore_mensal``."""

    valor_bruto: Decimal
    aliquota_inss: Decimal
    teto_previdenciario: Decimal
    teto_aplicado: bool
    base_inss: Decimal
    inss_socio: Decimal
    irrf: ResultadoIrrf
    valor_liquido: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_prolabore(
    valor_bruto: Decimal,
    teto_previdenciario: Decimal,
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
    *,
    aliquota_inss: Decimal = _ALIQ_DEFAULT,
) -> ResultadoProlabore:
    """Calcula pró-labore mensal — INSS 11% (plano simplificado) + IRRF.

    Args:
        valor_bruto: valor mensal definido em contrato social.
        teto_previdenciario: teto INSS vigente (vem de
            ``tabela_inss_faixa`` com ``tipo='contribuinte_individual'``).
        faixas_irrf: 5 faixas IRRF mensais vigentes.
        dependentes: dependentes IRRF do sócio.
        aliquota_inss: default 0,1100 (plano simplificado — Lei 9.876/1999).

    Returns:
        ResultadoProlabore.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if valor_bruto < _ZERO:
        raise ValueError(f"valor_bruto não pode ser negativo: {valor_bruto}")
    if teto_previdenciario <= _ZERO:
        raise ValueError(
            f"teto_previdenciario deve ser positivo: {teto_previdenciario}"
        )
    if aliquota_inss < _ZERO or aliquota_inss > Decimal("1"):
        raise ValueError(f"aliquota_inss fora de [0, 1]: {aliquota_inss}")
    if dependentes < 0:
        raise ValueError(f"dependentes não pode ser negativo: {dependentes}")

    teto_aplicado = valor_bruto > teto_previdenciario
    base_inss = teto_previdenciario if teto_aplicado else valor_bruto
    inss = _quantizar(base_inss * aliquota_inss)

    irrf = calcular_irrf_mensal(valor_bruto, inss, dependentes, faixas_irrf)
    valor_liquido = _quantizar(valor_bruto - inss - irrf.irrf)

    return ResultadoProlabore(
        valor_bruto=valor_bruto,
        aliquota_inss=aliquota_inss,
        teto_previdenciario=teto_previdenciario,
        teto_aplicado=teto_aplicado,
        base_inss=base_inss,
        inss_socio=inss,
        irrf=irrf,
        valor_liquido=valor_liquido,
    )
