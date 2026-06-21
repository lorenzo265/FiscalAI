"""Cálculo de férias — gozadas + 1/3 constitucional + abono pecuniário.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * CF art. 7º XVII — terço constitucional sobre férias.
  * CLT art. 129 e ss. — direito a 30 dias por ano (período aquisitivo
    completo, com até 5 faltas; até 14 faltas → 24 dias; até 23 → 18;
    até 32 → 12; +32 perde direito). PR2 assume período aquisitivo
    completo (30 dias) — controle do saldo de dias fica para o service.
  * CLT art. 143 — abono pecuniário: o empregado pode "vender" 1/3 dos
    dias (máx 10), recebendo em dinheiro o equivalente.
  * Lei 7.713/1988 art. 6º V + IN RFB 1.500 art. 11 — abono pecuniário
    de férias é ISENTO de IRRF.
  * IN RFB 971/2009 art. 58 — abono pecuniário NÃO integra a base de
    contribuição previdenciária (não incide INSS).
  * Lei 8.036/1990 art. 15 — FGTS 8% incide sobre remuneração paga em
    férias gozadas (incluindo o terço constitucional). NÃO incide sobre
    abono pecuniário (férias indenizadas/vendidas — STF RE 895.294).

Fórmulas:

  remuneracao_gozados = salario × dias_gozados / 30
  terco_gozados       = remuneracao_gozados / 3
  bruto_tributavel    = remuneracao_gozados + terco_gozados     ← INSS/IRRF/FGTS

  abono_dias          = salario × dias_vendidos / 30
  terco_abono         = abono_dias / 3
  abono_pecuniario    = abono_dias + terco_abono                ← isento

  base_fgts           = bruto_tributavel                        ← férias gozadas + 1/3
  fgts_empregador     = base_fgts × 8%

  inss   = calcular_inss_empregado(bruto_tributavel, ...)
  irrf   = calcular_irrf_mensal(bruto_tributavel, inss.inss, deps, ...,
             aplicar_redutor_lei_15270=aplicar_redutor_lei_15270)
  liquido = bruto_tributavel + abono_pecuniario − inss − irrf

  Redutor Lei 15.270/2025 (vigência 01/01/2026): referência = bruto_tributavel
  (= férias gozadas + 1/3 — o rendimento tributável bruto recebido no mês).
  O caller decide ativar via ``aplicar_redutor_lei_15270`` com base na
  competência: ``aplicar = (competencia >= date(2026, 1, 1))``.

Limites:
  * dias_gozados ∈ [1, 30].
  * dias_vendidos ∈ [0, 10] (CLT art. 143 §1º — máx 1/3).
  * dias_gozados + dias_vendidos ≤ 30.

Quantização: ``ROUND_HALF_EVEN`` 2 casas em cada componente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

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

getcontext().prec = 28

ALGORITMO_VERSAO = "ferias.v3"

_CENTAVO = Decimal("0.01")
_TRINTA = Decimal("30")
_TRES = Decimal("3")
_ZERO = Decimal("0")
_OITO_PCT = Decimal("0.0800")


@dataclass(frozen=True, slots=True)
class ResultadoFerias:
    """Snapshot do cálculo persistido em ``evento_folha`` (tipo='ferias')."""

    salario_base: Decimal
    dias_gozados: int
    dias_vendidos: int
    remuneracao_gozados: Decimal
    terco_gozados: Decimal
    bruto_tributavel: Decimal
    abono_pecuniario: Decimal  # parte isenta (dias vendidos + 1/3 sobre eles)
    inss: ResultadoInssEmpregado
    irrf: ResultadoIrrf
    # FGTS do empregador — Lei 8.036/90 art.15: 8% sobre férias gozadas + 1/3.
    # Abono pecuniário (dias_vendidos) NÃO integra base_fgts (verba indenizatória).
    base_fgts: Decimal
    fgts_empregador: Decimal
    valor_liquido: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_ferias(
    salario: Decimal,
    dias_gozados: int,
    dias_vendidos: int,
    faixas_inss: list[FaixaInss],
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
    *,
    aplicar_redutor_lei_15270: bool = False,
) -> ResultadoFerias:
    """Calcula um pagamento de férias.

    Args:
        salario: salário mensal de referência.
        dias_gozados: dias efetivamente gozados (1..30).
        dias_vendidos: dias convertidos em abono pecuniário (0..10).
        faixas_inss: 4 faixas vigentes na competência.
        faixas_irrf: 5 faixas vigentes na competência.
        dependentes: número de dependentes IRRF.
        aplicar_redutor_lei_15270: ativa o redutor mensal da Lei 15.270/2025.
            O caller (service) decide com base na competência:
            ``aplicar = (competencia >= date(2026, 1, 1))``.
            Referência do redutor = ``bruto_tributavel`` (férias gozadas + 1/3
            — o rendimento tributável bruto recebido no mês de férias).
            Default=False (backward-compatible — competências < 2026).

    Returns:
        ResultadoFerias.

    Raises:
        ValueError: parâmetros fora dos limites legais.
    """
    if salario < _ZERO:
        raise ValueError(f"salario não pode ser negativo: {salario}")
    if dias_gozados < 1 or dias_gozados > 30:
        raise ValueError(
            f"dias_gozados deve estar entre 1 e 30 (recebido {dias_gozados})"
        )
    if dias_vendidos < 0 or dias_vendidos > 10:
        raise ValueError(
            f"dias_vendidos deve estar entre 0 e 10 — CLT art. 143 §1º "
            f"(recebido {dias_vendidos})"
        )
    if dias_gozados + dias_vendidos > 30:
        raise ValueError(
            f"dias_gozados ({dias_gozados}) + dias_vendidos ({dias_vendidos}) "
            f"não pode passar de 30"
        )

    remun_gozados = salario * Decimal(dias_gozados) / _TRINTA
    terco_gozados = remun_gozados / _TRES
    bruto = _quantizar(remun_gozados + terco_gozados)

    if dias_vendidos == 0:
        abono = _ZERO
    else:
        abono_dias = salario * Decimal(dias_vendidos) / _TRINTA
        terco_abono = abono_dias / _TRES
        abono = _quantizar(abono_dias + terco_abono)

    inss = calcular_inss_empregado(bruto, faixas_inss)
    irrf = calcular_irrf_mensal(
        bruto,
        inss.inss,
        dependentes,
        faixas_irrf,
        aplicar_redutor_lei_15270=aplicar_redutor_lei_15270,
    )

    # FGTS: 8% sobre bruto tributável (férias gozadas + 1/3 constitucional).
    # Abono pecuniário NÃO integra base (verba indenizatória — STF RE 895.294).
    base_fgts = bruto
    fgts_empregador = _quantizar(base_fgts * _OITO_PCT)

    liquido = _quantizar(bruto + abono - inss.inss - irrf.irrf)

    return ResultadoFerias(
        salario_base=salario,
        dias_gozados=dias_gozados,
        dias_vendidos=dias_vendidos,
        remuneracao_gozados=_quantizar(remun_gozados),
        terco_gozados=_quantizar(terco_gozados),
        bruto_tributavel=bruto,
        abono_pecuniario=abono,
        inss=inss,
        irrf=irrf,
        base_fgts=base_fgts,
        fgts_empregador=fgts_empregador,
        valor_liquido=liquido,
    )
