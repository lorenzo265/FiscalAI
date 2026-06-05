"""Cálculo de distribuição de lucros para sócio.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 10 — lucros distribuídos por PJ a sócio pessoa física
    são ISENTOS de IRRF e não integram a base do IR do beneficiário, desde
    que dentro do limite contábil (lucro líquido apurado).
  * Para empresas SEM escrituração contábil completa (regra geral para SN e
    LP que não optam por contabilidade formal): o limite isento é a presunção
    do lucro do regime menos os impostos pagos (IRPJ + CSLL + PIS + COFINS).
  * Para empresas COM escrituração contábil completa: o limite é o lucro
    líquido contábil do exercício/período (RIR/2018 art. 238).
  * Excesso ao limite: tributado como rendimento comum (faixa IRRF mensal),
    com retenção na fonte e ajuste na declaração anual (PF).

Estratégia do PR3:
  * O ``limite_isento`` é INPUT — calculado externamente pelo service ou
    pelo contador (depende de base contábil/presunção da empresa, que
    pertence ao módulo ``relatorios`` da Sprint 12).
  * Algoritmo decide split isento/tributável e aplica IRRF se houver
    excedente (alíquota progressiva mensal — usa mesma tabela do CLT).

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

from app.modules.pessoal.calcula_irrf import (
    FaixaIrrf,
    ResultadoIrrf,
    calcular_irrf_mensal,
)

getcontext().prec = 28

ALGORITMO_VERSAO = "distribuicao.v2"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


class BaseCalculoReferencia(StrEnum):
    PRESUNCAO_LP = "presuncao_lp"
    SIMPLES_DENTRO_DAS = "simples_dentro_das"
    LUCRO_CONTABIL = "lucro_contabil"
    MEI = "mei"


@dataclass(frozen=True, slots=True)
class ResultadoDistribuicao:
    """Snapshot persistido em ``distribuicao_lucros``."""

    valor_distribuido: Decimal
    limite_isento_apurado: Decimal
    valor_isento: Decimal
    valor_tributavel: Decimal
    base_calculo_referencia: BaseCalculoReferencia
    irrf_excedente: ResultadoIrrf | None  # None se não houver excedente
    irrf_retido: Decimal
    valor_liquido_socio: Decimal  # bruto − irrf
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_distribuicao(
    valor_distribuido: Decimal,
    limite_isento_apurado: Decimal,
    base_calculo_referencia: BaseCalculoReferencia,
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
) -> ResultadoDistribuicao:
    """Decide split isento/tributável e calcula IRRF sobre o excedente.

    Args:
        valor_distribuido: total bruto que será distribuído ao sócio.
        limite_isento_apurado: limite contábil (presunção − impostos, ou
            lucro líquido contábil) para fins de Lei 9.249/1995 art. 10.
        base_calculo_referencia: rótulo do método usado pelo serviço para
            apurar o limite — persistido para auditoria.
        faixas_irrf: tabela mensal vigente (aplicada apenas se houver
            excedente sobre o limite).
        dependentes: dependentes IRRF do sócio.

    Returns:
        ResultadoDistribuicao.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if valor_distribuido < _ZERO:
        raise ValueError(
            f"valor_distribuido não pode ser negativo: {valor_distribuido}"
        )
    if limite_isento_apurado < _ZERO:
        raise ValueError(
            f"limite_isento_apurado não pode ser negativo: {limite_isento_apurado}"
        )
    if dependentes < 0:
        raise ValueError(f"dependentes não pode ser negativo: {dependentes}")

    valor_isento = min(valor_distribuido, limite_isento_apurado)
    # m6 FA8: quantizar valor_tributavel ANTES de passar ao IRRF.
    # Se limite_isento_apurado vier com >2 casas decimais (e.g. de
    # receita×presunção em calcula_limite_isento), a subtração produziria
    # base com casas extras → centavo divergente no IRRF. Quantizamos aqui
    # na fronteira, conforme ROUND_HALF_EVEN (padrão fiscal do sistema).
    valor_tributavel = _quantizar(valor_distribuido - valor_isento)

    if valor_tributavel == _ZERO:
        irrf_obj: ResultadoIrrf | None = None
        irrf_retido = _ZERO
    else:
        # Excedente é tratado como rendimento mensal — sem dedução de INSS
        # (já paga na fonte da empresa, distinto do tributo do sócio).
        # Valor já quantizado (2 casas) para garantir base limpa ao IRRF.
        irrf_obj = calcular_irrf_mensal(
            valor_tributavel, _ZERO, dependentes, faixas_irrf
        )
        irrf_retido = irrf_obj.irrf

    valor_liquido = _quantizar(valor_distribuido - irrf_retido)

    return ResultadoDistribuicao(
        valor_distribuido=valor_distribuido,
        limite_isento_apurado=limite_isento_apurado,
        valor_isento=_quantizar(valor_isento),
        valor_tributavel=_quantizar(valor_tributavel),
        base_calculo_referencia=base_calculo_referencia,
        irrf_excedente=irrf_obj,
        irrf_retido=irrf_retido,
        valor_liquido_socio=valor_liquido,
    )
