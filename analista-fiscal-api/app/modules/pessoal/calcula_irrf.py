"""Cálculo do IRRF mensal — empregado CLT.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 14.848/2024 — atualizou faixas vigentes.
  * MP 1.171/2024 — convertida na referida lei; ampliou isenção até R$ 2.259,20.
  * IN RFB 1.500/2014 (consolidação) + RIR 2018 art. 700.

Fórmula:

    base_irrf = salario_bruto
              − inss_empregado
              − (dependentes × deducao_dependente_mensal)
              − pensao_alimenticia      (não tratada neste PR)

    Encontra a faixa cuja ``base_ate >= base_irrf`` (ordenadas crescentes).
    irrf = max(0, base_irrf × aliquota_faixa − parcela_deduzir_faixa)

  Faixa 1 (isenta) → aliquota=0, parcela_deduzir=0 → irrf=0 automaticamente.

Quantização: ``ROUND_HALF_EVEN`` 2 casas no resultado final.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "irrf.mensal.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class FaixaIrrf:
    """Linha de ``tabela_irrf_faixa`` (SCD Type 2 — vem do banco)."""

    faixa: int  # 1..5
    base_ate: Decimal
    aliquota: Decimal  # fração: 0.0750 = 7,5%
    parcela_deduzir: Decimal
    deducao_dependente: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoIrrf:
    """Snapshot do cálculo persistido no holerite."""

    salario_bruto: Decimal
    inss_empregado: Decimal
    dependentes: int
    deducao_dependentes: Decimal
    base_irrf: Decimal
    faixa: int
    aliquota: Decimal
    parcela_deduzir: Decimal
    irrf: Decimal  # valor a reter (BRL, 2 casas)
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_irrf_mensal(
    salario_bruto: Decimal,
    inss_empregado: Decimal,
    dependentes: int,
    faixas: list[FaixaIrrf],
) -> ResultadoIrrf:
    """Calcula o IRRF mensal a reter.

    Args:
        salario_bruto: rendimento tributável bruto do mês.
        inss_empregado: INSS já retido (dedutível da base — IN RFB 1.500 art. 52).
        dependentes: número de dependentes para fins de IRRF.
        faixas: 5 faixas vigentes na competência. Vêm de ``tabela_irrf_faixa``
                filtrada por vigência. Todas compartilham a mesma
                ``deducao_dependente`` (uniforme na legislação atual).

    Returns:
        ResultadoIrrf com base, faixa e valor.

    Raises:
        ValueError: se valores negativos ou ``faixas`` vazia.
    """
    if salario_bruto < _ZERO:
        raise ValueError(f"salario_bruto não pode ser negativo: {salario_bruto}")
    if inss_empregado < _ZERO:
        raise ValueError(f"inss_empregado não pode ser negativo: {inss_empregado}")
    if dependentes < 0:
        raise ValueError(f"dependentes não pode ser negativo: {dependentes}")
    if not faixas:
        raise ValueError("faixas não pode ser vazia")

    ordenadas = sorted(faixas, key=lambda f: f.faixa)
    ded_por_dep = ordenadas[0].deducao_dependente
    deducao_dependentes = ded_por_dep * Decimal(dependentes)

    base = salario_bruto - inss_empregado - deducao_dependentes
    if base < _ZERO:
        base = _ZERO

    faixa_obj = _encontrar_faixa(base, ordenadas)
    irrf_bruto = base * faixa_obj.aliquota - faixa_obj.parcela_deduzir
    if irrf_bruto < _ZERO:
        irrf_bruto = _ZERO
    irrf = irrf_bruto.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)

    return ResultadoIrrf(
        salario_bruto=salario_bruto,
        inss_empregado=inss_empregado,
        dependentes=dependentes,
        deducao_dependentes=deducao_dependentes.quantize(
            _CENTAVO, rounding=ROUND_HALF_EVEN
        ),
        base_irrf=base.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN),
        faixa=faixa_obj.faixa,
        aliquota=faixa_obj.aliquota,
        parcela_deduzir=faixa_obj.parcela_deduzir,
        irrf=irrf,
    )


def _encontrar_faixa(base: Decimal, faixas: list[FaixaIrrf]) -> FaixaIrrf:
    for f in faixas:
        if base <= f.base_ate:
            return f
    return faixas[-1]
