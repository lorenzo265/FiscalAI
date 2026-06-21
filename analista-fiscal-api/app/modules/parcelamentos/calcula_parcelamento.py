"""Cálculo de cronograma de parcelamento fiscal.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 10.522/2002 art. 10 — parcelamento ordinário: até 60 parcelas
    mensais e sucessivas para débitos da RFB e da PGFN.
  * Lei 10.522/2002 art. 14 — parcela mínima:
      R$ 200,00 para pessoa jurídica;
      R$ 100,00 para pessoa física;
      em casos especiais a lei permite valores maiores (não modelados aqui).
  * Lei 11.941/2009, Lei 12.996/2014, Lei 13.043/2014 (PERT), Lei 13.496/2017
    (PERT2) — modalidades especiais com prazo até 240 meses e regras
    diferenciadas. PR3 modela ordinário; PERT/PERT2 ficam para sprint futura.
  * IN RFB 2.063/2022 — regula consolidação e taxa SELIC + 1% no mês.

Modelo PR3 (ordinário, sem projeção SELIC mês a mês):

  parcela_base = divida_consolidada / num_parcelas
  parcela_base ≥ R$200 (PJ)
  vencimentos:  primeira no mesmo dia do mês seguinte à adesão; demais
                seguem o mesmo dia útil dos meses subsequentes.

A projeção SELIC (juros que correm sobre o saldo) e a parcela do "mês de
pagamento" com SELIC acumulada + 1% ficam para uma sprint futura, quando
a tabela ``selic_mensal`` (já existente) for usada de fato. Por ora o
sistema apenas mostra ``parcela_base`` para fins de planejamento.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

from app.modules.agenda.gerar_calendario import _proximo_dia_util

getcontext().prec = 28

ALGORITMO_VERSAO = "parcelamento.ordinario.v3"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_PARCELA_MINIMA_PJ = Decimal("200.00")
_PARCELA_MINIMA_PF = Decimal("100.00")
_MAX_PARCELAS_ORDINARIO = 60


class TipoContribuinte(StrEnum):
    PJ = "pj"
    PF = "pf"


@dataclass(frozen=True, slots=True)
class ParcelaProjetada:
    numero: int
    vencimento: date
    valor_projetado: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoParcelamento:
    divida_consolidada: Decimal
    num_parcelas: int
    parcela_base: Decimal
    parcela_minima_aplicavel: Decimal
    data_adesao: date
    parcelas: tuple[ParcelaProjetada, ...]
    algoritmo_versao: str = ALGORITMO_VERSAO


_FERIADOS_VAZIO: frozenset[date] = frozenset()


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def gerar_parcelamento_ordinario(
    divida_consolidada: Decimal,
    num_parcelas: int,
    data_adesao: date,
    *,
    contribuinte: TipoContribuinte = TipoContribuinte.PJ,
    feriados: Iterable[date] | None = None,
) -> ResultadoParcelamento:
    """Gera cronograma de parcelamento ordinário.

    Args:
        divida_consolidada: valor total a parcelar (somatório do principal,
            multa e juros consolidados na adesão).
        num_parcelas: 1..60 (limite do ordinário).
        data_adesao: data de adesão; 1ª parcela vence no mesmo dia do mês
            seguinte (ou último dia do mês, se inexistente), postergado
            para o próximo dia útil quando cair em sábado/domingo/feriado
            (IN RFB 1.300/2012 art. 26).
        contribuinte: PJ (mín. R$200) ou PF (mín. R$100).
        feriados: feriados nacionais a considerar na postergação de dia não-útil.
            Quando ``None``, somente sábados e domingos são postergados.

    Returns:
        ResultadoParcelamento.

    Raises:
        ValueError: parâmetros inválidos ou parcela_base < parcela_minima.
    """
    if divida_consolidada <= _ZERO:
        raise ValueError(
            f"divida_consolidada deve ser positiva: {divida_consolidada}"
        )
    if num_parcelas < 1 or num_parcelas > _MAX_PARCELAS_ORDINARIO:
        raise ValueError(
            f"num_parcelas deve estar entre 1 e {_MAX_PARCELAS_ORDINARIO} "
            f"(ordinário Lei 10.522/2002); recebido {num_parcelas}"
        )

    feriados_set: frozenset[date] = (
        frozenset(feriados) if feriados is not None else _FERIADOS_VAZIO
    )

    minima = (
        _PARCELA_MINIMA_PJ
        if contribuinte is TipoContribuinte.PJ
        else _PARCELA_MINIMA_PF
    )
    parcela_base = _quantizar(divida_consolidada / Decimal(num_parcelas))

    if parcela_base < minima:
        raise ValueError(
            f"parcela_base {parcela_base} < mínima {minima} para {contribuinte.value}. "
            f"Reduza num_parcelas ou aumente o valor."
        )

    # Reconciliação de centavos: a última parcela absorve o resíduo de arredondamento
    # para garantir que sum(parcelas) == divida_consolidada (ex.: R$1000/3 = 333,33×3
    # = 999,99 vs 333,33×2 + 333,34 = 1000,00).
    ultima_parcela = divida_consolidada - parcela_base * Decimal(num_parcelas - 1)

    parcelas_list: list[ParcelaProjetada] = []
    for n in range(1, num_parcelas + 1):
        valor = ultima_parcela if n == num_parcelas else parcela_base
        parcelas_list.append(
            ParcelaProjetada(
                numero=n,
                vencimento=_proximo_vencimento(data_adesao, n, feriados_set),
                valor_projetado=valor,
            )
        )
    parcelas = tuple(parcelas_list)

    # Invariante: reconciliação deve ser exata.
    soma = sum(p.valor_projetado for p in parcelas)
    assert soma == divida_consolidada, (
        f"Erro de reconciliação: sum(parcelas)={soma} != divida_consolidada={divida_consolidada}"
    )

    return ResultadoParcelamento(
        divida_consolidada=divida_consolidada,
        num_parcelas=num_parcelas,
        parcela_base=parcela_base,
        parcela_minima_aplicavel=minima,
        data_adesao=data_adesao,
        parcelas=parcelas,
    )


def _proximo_vencimento(
    adesao: date, n: int, feriados: frozenset[date] = _FERIADOS_VAZIO
) -> date:
    """1ª parcela vence no mesmo dia do mês seguinte à adesão; e assim por diante.

    Se o dia não existe no mês alvo (ex.: 31 em fevereiro), usa o último dia.
    Em seguida, posterga para o próximo dia útil quando cair em sábado,
    domingo ou feriado nacional (IN RFB 1.300/2012 art. 26).
    """
    novo_mes = adesao.month + n
    novo_ano = adesao.year + (novo_mes - 1) // 12
    novo_mes_norm = ((novo_mes - 1) % 12) + 1
    dia = adesao.day
    ultimo_dia = _ultimo_dia_do_mes(novo_ano, novo_mes_norm)
    candidato = date(novo_ano, novo_mes_norm, min(dia, ultimo_dia))
    return _proximo_dia_util(candidato, feriados)


_DIAS_POR_MES = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _ultimo_dia_do_mes(ano: int, mes: int) -> int:
    if mes == 2 and _ano_bissexto(ano):
        return 29
    return _DIAS_POR_MES[mes - 1]


def _ano_bissexto(ano: int) -> bool:
    return (ano % 4 == 0 and ano % 100 != 0) or (ano % 400 == 0)
