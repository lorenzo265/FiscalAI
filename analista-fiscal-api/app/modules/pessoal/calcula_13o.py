"""Cálculo do 13º salário — 1ª e 2ª parcelas.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 4.090/1962 — institui a gratificação natalina (13º).
  * Decreto 57.155/1965 — regulamenta o pagamento (1ª parcela 1/fev a 30/nov;
    2ª parcela até 20/dez).
  * Lei 8.134/1990 art. 16 — tributação EXCLUSIVA NA FONTE para IRRF do 13º
    (não soma à renda mensal — cálculo separado com tabela mensal vigente
    em dezembro).
  * CLT art. 7º VIII (CF) — base proporcional: avos = meses trabalhados no
    ano (15+ dias num mês contam como mês integral — regra dos 15 dias).

Fórmulas:

  base_13 = salario × avos / 12

  primeira_parcela = base_13 / 2                              (sem desconto)
  inss_13          = calcular_inss_empregado(base_13, ...)    (escalonado)
  irrf_13          = calcular_irrf_mensal(
                       base_13, inss_13.inss, dependentes, ...)
  segunda_parcela  = base_13 − primeira_paga − inss_13 − irrf_13

Observação: ``primeira_paga`` é input do cálculo da 2ª — se a 1ª foi
adiantada em valor diferente de ``base/2`` (acordo individual), o sistema
respeita o que foi efetivamente pago.

Quantização: ``ROUND_HALF_EVEN`` 2 casas no resultado de cada componente.
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

ALGORITMO_VERSAO = "13o.v1"

_CENTAVO = Decimal("0.01")
_DOZE = Decimal("12")
_DOIS = Decimal("2")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Resultado13oPrimeira:
    """Resultado da 1ª parcela (sem desconto INSS/IRRF)."""

    salario_base: Decimal
    avos: int
    base_proporcional: Decimal
    valor_primeira_parcela: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


@dataclass(frozen=True, slots=True)
class Resultado13oSegunda:
    """Resultado da 2ª parcela (com INSS escalonado + IRRF exclusivo)."""

    salario_base: Decimal
    avos: int
    base_proporcional: Decimal
    primeira_parcela_paga: Decimal
    inss: ResultadoInssEmpregado
    irrf: ResultadoIrrf
    valor_segunda_parcela: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _validar_avos(avos: int) -> None:
    if avos < 1 or avos > 12:
        raise ValueError(f"avos deve estar entre 1 e 12 (recebido {avos})")


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_13o_primeira(
    salario: Decimal,
    avos: int,
) -> Resultado13oPrimeira:
    """Calcula a 1ª parcela do 13º (paga entre 1/fev e 30/nov).

    Args:
        salario: salário mensal usado como base (geralmente o de novembro).
        avos: meses trabalhados no ano (1..12), aplicando a regra dos 15 dias.

    Returns:
        Resultado13oPrimeira.

    Raises:
        ValueError: se ``salario`` negativo ou ``avos`` fora de [1, 12].
    """
    if salario < _ZERO:
        raise ValueError(f"salario não pode ser negativo: {salario}")
    _validar_avos(avos)

    base = _quantizar(salario * Decimal(avos) / _DOZE)
    primeira = _quantizar(base / _DOIS)

    return Resultado13oPrimeira(
        salario_base=salario,
        avos=avos,
        base_proporcional=base,
        valor_primeira_parcela=primeira,
    )


def calcular_13o_segunda(
    salario: Decimal,
    avos: int,
    primeira_parcela_paga: Decimal,
    faixas_inss: list[FaixaInss],
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
) -> Resultado13oSegunda:
    """Calcula a 2ª parcela do 13º (paga até 20/dez).

    Aplica INSS escalonado e IRRF EXCLUSIVO NA FONTE sobre a base integral
    do 13º. A primeira parcela paga é deduzida do valor a pagar.

    Args:
        salario: salário base (geralmente o de dezembro).
        avos: meses trabalhados (1..12).
        primeira_parcela_paga: valor efetivamente adiantado em 1ª parcela.
        faixas_inss: 4 faixas vigentes em dezembro.
        faixas_irrf: 5 faixas vigentes em dezembro.
        dependentes: número de dependentes IRRF.

    Returns:
        Resultado13oSegunda.

    Raises:
        ValueError: parâmetros fora de domínio.
    """
    if salario < _ZERO:
        raise ValueError(f"salario não pode ser negativo: {salario}")
    if primeira_parcela_paga < _ZERO:
        raise ValueError(
            f"primeira_parcela_paga não pode ser negativa: {primeira_parcela_paga}"
        )
    _validar_avos(avos)

    base = _quantizar(salario * Decimal(avos) / _DOZE)
    inss = calcular_inss_empregado(base, faixas_inss)
    irrf = calcular_irrf_mensal(base, inss.inss, dependentes, faixas_irrf)

    segunda = _quantizar(base - primeira_parcela_paga - inss.inss - irrf.irrf)

    return Resultado13oSegunda(
        salario_base=salario,
        avos=avos,
        base_proporcional=base,
        primeira_parcela_paga=primeira_parcela_paga,
        inss=inss,
        irrf=irrf,
        valor_segunda_parcela=segunda,
    )
