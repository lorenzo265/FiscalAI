"""Algoritmo puro de depreciação linear — IN SRF 162/1998 art. 305.

Zero I/O. Decimal-safe. Determinístico.

Método linear:
    parcela_mensal = (valor_aquisicao − valor_residual) / vida_util_meses

Regras de borda:

  * Mês de aquisição **NÃO** deprecia — IN SRF 162/1998 permite começar no mês
    seguinte à instalação. Simplifica o algoritmo e bate com a prática contábil
    da maioria das empresas (pro-rata-die é opcional, raramente usado).

  * Depreciação cessa quando:
      a) ``valor_acumulado`` atinge ``valor_aquisicao − valor_residual``; ou
      b) ``data_baixa`` foi definida e a competência é >= data_baixa; ou
      c) ``ativo`` é False.

  * A última parcela é ajustada para fechar exatamente em
    ``valor_aquisicao − valor_residual`` — evita resíduo por arredondamento.

  * Valores quantizados a 2 casas, arredondamento ROUND_HALF_EVEN (banker's).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

ALGORITMO_VERSAO = "depr-linear-2026.05"

_CENTAVO = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class BemView:
    """Subset imutável de ``BemImobilizado`` usado pelo algoritmo."""

    valor_aquisicao: Decimal
    valor_residual: Decimal
    vida_util_meses: int
    data_aquisicao: date
    data_baixa: date | None
    ativo: bool


@dataclass(frozen=True, slots=True)
class ResultadoDepreciacao:
    """Resultado de uma competência específica.

    ``valor_depreciado`` é zero quando o bem não deve depreciar naquele mês
    (antes da elegibilidade, após baixa, totalmente depreciado).
    """

    valor_depreciado: Decimal
    valor_acumulado: Decimal
    saldo_contabil: Decimal
    eh_ultima_parcela: bool
    versao: str = ALGORITMO_VERSAO


def deve_depreciar_competencia(bem: BemView, competencia: date) -> bool:
    """Indica se o bem está em janela de depreciação na competência dada.

    Regras combinadas (todas precisam ser True):
      * ``ativo`` é True.
      * Competência > mês de aquisição (não depreciamos no mês 0).
      * Sem data_baixa OU competência < mês de baixa.
    """
    if not bem.ativo:
        return False

    competencia_inicial = _primeiro_dia_mes_seguinte(bem.data_aquisicao)
    if competencia < competencia_inicial:
        return False

    if bem.data_baixa is not None:
        mes_baixa = date(bem.data_baixa.year, bem.data_baixa.month, 1)
        if competencia >= mes_baixa:
            return False

    return True


def calcular_parcela_mensal(
    bem: BemView,
    competencia: date,
    *,
    valor_acumulado_anterior: Decimal,
) -> ResultadoDepreciacao:
    """Calcula a parcela do mês.

    Args:
        bem: snapshot imutável do bem.
        competencia: 1º dia do mês a depreciar.
        valor_acumulado_anterior: depreciação acumulada até o mês anterior.
            Vem do ``DepreciacaoRepo.buscar_acumulado_ate``.
    """
    base_depreciavel = bem.valor_aquisicao - bem.valor_residual

    # Já totalmente depreciado.
    if valor_acumulado_anterior >= base_depreciavel:
        return ResultadoDepreciacao(
            valor_depreciado=Decimal("0.00"),
            valor_acumulado=base_depreciavel,
            saldo_contabil=bem.valor_aquisicao - base_depreciavel,
            eh_ultima_parcela=False,
        )

    if not deve_depreciar_competencia(bem, competencia):
        return ResultadoDepreciacao(
            valor_depreciado=Decimal("0.00"),
            valor_acumulado=valor_acumulado_anterior,
            saldo_contabil=bem.valor_aquisicao - valor_acumulado_anterior,
            eh_ultima_parcela=False,
        )

    parcela_padrao = (base_depreciavel / Decimal(bem.vida_util_meses)).quantize(
        _CENTAVO, rounding=ROUND_HALF_EVEN
    )

    # Última parcela: fecha resíduo de arredondamento. Critérios cumulativos:
    #   a) Já foram feitas (vida_util_meses - 1) parcelas com base na competência
    #      (meses decorridos desde a elegibilidade); ou
    #   b) A parcela padrão sozinha já cobre o restante.
    #
    # FIX #5 (PR6): derivamos o número de parcelas anteriores a partir da
    # competência — não da divisão do valor acumulado pela parcela padrão,
    # que pode errar por 1 quando os centavos de ROUND_HALF_EVEN se acumulam
    # (ex.: parcela_padrao=333,33 → acumulado_2=666,66 → 666,66/333,33=2,0,
    # mas no mês 59 o acumulado pode cair no arredondamento).
    restante = base_depreciavel - valor_acumulado_anterior
    competencia_inicial = _primeiro_dia_mes_seguinte(bem.data_aquisicao)
    # Meses decorridos entre a competência inicial e a competência atual (inclusive).
    meses_desde_inicio = (
        (competencia.year - competencia_inicial.year) * 12
        + (competencia.month - competencia_inicial.month)
    )
    parcelas_anteriores = meses_desde_inicio  # quantas competências ANTES desta
    eh_ultima_por_contagem = parcelas_anteriores + 1 >= bem.vida_util_meses
    eh_ultima_por_valor = parcela_padrao >= restante

    if eh_ultima_por_contagem or eh_ultima_por_valor:
        valor_depreciado = restante
        eh_ultima = True
    else:
        valor_depreciado = parcela_padrao
        eh_ultima = False

    valor_acumulado = valor_acumulado_anterior + valor_depreciado
    saldo_contabil = bem.valor_aquisicao - valor_acumulado

    return ResultadoDepreciacao(
        valor_depreciado=valor_depreciado,
        valor_acumulado=valor_acumulado,
        saldo_contabil=saldo_contabil,
        eh_ultima_parcela=eh_ultima,
    )


def _primeiro_dia_mes_seguinte(d: date) -> date:
    """Retorna o 1º dia do mês posterior a ``d``."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)
