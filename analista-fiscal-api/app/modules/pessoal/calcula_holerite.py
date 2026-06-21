"""Orquestrador puro do cálculo de holerite mensal.

Camada 1 (determinística). Zero I/O — recebe tabelas tributárias já carregadas.

Cobertura do PR1: empregado CLT com salário fixo. Não trata neste PR:
  * Horas extras, adicionais (noturno, periculosidade, insalubridade) — PR2.
  * 13º, férias, rescisão — PR2.
  * Pró-labore (cálculo INSS 11% + IRRF) — PR3.
  * Pensão alimentícia (dedução adicional na base IRRF) — backlog.

Sequência do cálculo (ordem importa: IRRF depende do INSS):

  1. salario_bruto = salario_base (PR1 — só salário fixo)
  2. inss = calcular_inss_empregado(...)
  3. irrf = calcular_irrf_mensal(salario_bruto, inss.inss, dependentes, ...,
             aplicar_redutor_lei_15270=aplicar_redutor_lei_15270)
  4. fgts = calcular_fgts(...)
  5. liquido = salario_bruto − inss − irrf
  6. Quantização final em 2 casas.

Redutor Lei 15.270/2025 (vigência 01/01/2026):
  O parâmetro ``aplicar_redutor_lei_15270`` expõe a ativação para o caller.
  O service decide com base na competência:
      aplicar = (competencia >= date(2026, 1, 1))
  A referência do redutor é o salário bruto mensal (rendimento tributável
  bruto — texto RFB: "o salário, não a base de cálculo").
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from app.modules.pessoal.calcula_fgts import (
    ResultadoFgts,
    calcular_fgts,
)
from app.modules.pessoal.calcula_inss import (
    FaixaInss,
    ResultadoInssEmpregado,
    calcular_inss_empregado,
)
from app.modules.pessoal.calcula_irrf import (
    FaixaIrrf,
    ResultadoIrrf,
    calcular_irrf_mensal,
)

ALGORITMO_VERSAO = "holerite.clt.v2"

_CENTAVO = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ResultadoHolerite:
    """Snapshot completo persistido em ``holerite`` (Sprint 10 PR1)."""

    salario_base: Decimal
    salario_bruto: Decimal
    inss: ResultadoInssEmpregado
    irrf: ResultadoIrrf
    fgts: ResultadoFgts
    valor_liquido: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_holerite(
    salario_base: Decimal,
    dependentes_irrf: int,
    faixas_inss: list[FaixaInss],
    faixas_irrf: list[FaixaIrrf],
    aliquota_fgts: Decimal,
    *,
    vinculo: str = "clt",
    aplicar_redutor_lei_15270: bool = False,
) -> ResultadoHolerite:
    """Calcula um holerite mensal completo a partir das tabelas vigentes.

    Args:
        salario_base: salário do funcionário (PR1: igual ao bruto).
        dependentes_irrf: número de dependentes para dedução de IRRF.
        faixas_inss: 4 faixas vigentes (tipo='empregado').
        faixas_irrf: 5 faixas vigentes.
        aliquota_fgts: alíquota vigente do vínculo.
        vinculo: vínculo para fins de FGTS / persistência.
        aplicar_redutor_lei_15270: ativa o redutor mensal da Lei 15.270/2025.
            O caller (service) decide com base na competência:
            ``aplicar = (competencia >= date(2026, 1, 1))``.
            Default=False (backward-compatible — competências < 2026).

    Returns:
        ResultadoHolerite completo.
    """
    salario_bruto = salario_base

    inss = calcular_inss_empregado(salario_bruto, faixas_inss)
    irrf = calcular_irrf_mensal(
        salario_bruto,
        inss.inss,
        dependentes_irrf,
        faixas_irrf,
        aplicar_redutor_lei_15270=aplicar_redutor_lei_15270,
    )
    fgts = calcular_fgts(salario_bruto, aliquota_fgts, vinculo=vinculo)

    liquido = (salario_bruto - inss.inss - irrf.irrf).quantize(
        _CENTAVO, rounding=ROUND_HALF_EVEN
    )

    return ResultadoHolerite(
        salario_base=salario_base,
        salario_bruto=salario_bruto,
        inss=inss,
        irrf=irrf,
        fgts=fgts,
        valor_liquido=liquido,
    )
