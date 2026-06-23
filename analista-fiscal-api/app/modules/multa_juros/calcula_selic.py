"""Cálculo de multa e juros de mora para tributos federais — função pura.

Mora ordinária (pagamento em atraso sem denúncia espontânea):
  Base legal: Lei 9.430/1996, art. 61, §2º; IN RFB 1.910/2019; Sicalc.
  - Multa de mora: 0,33%/dia, teto 20% (atingido no ~61º dia)
  - Juros de mora: SELIC acumulada a partir do 1º dia do mês seguinte ao vencimento
  - Mês de pagamento: adicionar 1% fixo (independente de SELIC do mês corrente)

Denúncia espontânea (CTN art. 138):
  - Multa EXCLUÍDA — contribuinte confessa antes de qualquer ato fiscal de ofício
  - Juros SELIC mantidos — correção monetária, não penalidade
  - Mês de pagamento: 1% mantido

Todos os cálculos com Decimal — nunca float (§8 anti-stack).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "mora.sicalc.v2"


@dataclass(frozen=True)
class ResultadoMora:
    valor_original: Decimal
    multa_mora: Decimal            # 0,33%/dia até 20%; zero em denúncia espontânea
    juros_selic: Decimal           # SELIC acumulada (meses cheios pós-vencimento)
    acrescimo_mes_pagamento: Decimal  # 1% fixo no mês corrente do pagamento
    total_acrescimos: Decimal
    valor_atualizado: Decimal
    dias_atraso: int
    meses_selic: int               # meses completos entre vencimento e pagamento
    aliquota_multa: Decimal        # multa efetiva aplicada (max 20%)
    aliquota_juros_acumulada: Decimal  # SELIC somada sem composição (metodologia Sicalc)
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_mora(
    valor: Decimal,
    data_vencimento: date,
    data_pagamento: date,
    taxas_selic: list[tuple[date, Decimal]],
) -> ResultadoMora:
    """Multa + juros SELIC para pagamento em atraso (Lei 9.430/1996, art. 61, §2º).

    Args:
        valor: Valor principal do tributo (NUNCA float).
        data_vencimento: Data de vencimento original do tributo.
        data_pagamento: Data do pagamento (deve ser >= data_vencimento).
        taxas_selic: Lista de (competencia_1o_dia, taxa_mensal) ordenada por competencia.
                     Competência = 1º dia do mês ao qual a taxa se aplica.

    Returns:
        ResultadoMora com todos os componentes discriminados.

    Raises:
        ValueError: Se pagamento for anterior ao vencimento, ou SELIC insuficiente.
    """
    if data_pagamento < data_vencimento:
        raise ValueError(
            f"data_pagamento ({data_pagamento}) anterior a data_vencimento ({data_vencimento})"
        )

    dias_atraso = (data_pagamento - data_vencimento).days

    # Sem atraso — sem multa e sem juros
    if dias_atraso == 0:
        zero = Decimal("0")
        return ResultadoMora(
            valor_original=valor,
            multa_mora=zero,
            juros_selic=zero,
            acrescimo_mes_pagamento=zero,
            total_acrescimos=zero,
            valor_atualizado=valor,
            dias_atraso=0,
            meses_selic=0,
            aliquota_multa=zero,
            aliquota_juros_acumulada=zero,
        )

    # ── Multa de mora ─────────────────────────────────────────────────────────
    # 0,33% ao dia; teto 20% (atingido no ~61º dia — Lei 9.430/1996, art. 61, §2º)
    taxa_diaria_multa = Decimal("0.0033")
    aliquota_multa = min(taxa_diaria_multa * dias_atraso, Decimal("0.20"))
    multa_mora = (valor * aliquota_multa).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    # ── Juros SELIC ───────────────────────────────────────────────────────────
    # Meses cheios a partir do 1º dia do mês seguinte ao vencimento
    # até o mês anterior ao pagamento (mês do pagamento = 1% fixo)
    venc_mes_seguinte = primeiro_dia_mes_seguinte(data_vencimento)
    pagamento_mes_atual = date(data_pagamento.year, data_pagamento.month, 1)

    # Converte taxas para dict para lookup rápido
    selic_dict: dict[date, Decimal] = dict(taxas_selic)

    aliquota_selic_acumulada = Decimal("0")
    meses_selic = 0

    mes_iter = venc_mes_seguinte
    while mes_iter < pagamento_mes_atual:
        taxa = selic_dict.get(mes_iter)
        if taxa is None:
            raise ValueError(
                f"Taxa SELIC não disponível para competência {mes_iter}. "
                "Preencha a tabela selic_mensal antes de calcular mora."
            )
        aliquota_selic_acumulada += taxa
        meses_selic += 1
        mes_iter = primeiro_dia_mes_seguinte(mes_iter)

    juros_selic = (valor * aliquota_selic_acumulada).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    # ── Acréscimo do mês de pagamento: 1% fixo (Sicalc) ─────────────────────
    # Lei 9.430/1996 art. 61 §3º + metodologia Sicalc: os juros de mora
    # (SELIC acumulada + 1% do mês de pagamento) só incidem a partir do 1º dia
    # do mês SUBSEQUENTE ao vencimento.  Pagamento dentro do mesmo mês do
    # vencimento → apenas multa de mora (0,33%/dia); juros = 0.
    pagamento_mes_1 = date(data_pagamento.year, data_pagamento.month, 1)
    vencimento_mes_1 = date(data_vencimento.year, data_vencimento.month, 1)
    if pagamento_mes_1 > vencimento_mes_1:
        acrescimo_mes = (valor * Decimal("0.01")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
    else:
        # Mesmo mês: sem juros (1% nem SELIC — não há mês subsequente fechado)
        acrescimo_mes = Decimal("0")

    total_acrescimos = multa_mora + juros_selic + acrescimo_mes
    valor_atualizado = valor + total_acrescimos

    return ResultadoMora(
        valor_original=valor,
        multa_mora=multa_mora,
        juros_selic=juros_selic,
        acrescimo_mes_pagamento=acrescimo_mes,
        total_acrescimos=total_acrescimos,
        valor_atualizado=valor_atualizado,
        dias_atraso=dias_atraso,
        meses_selic=meses_selic,
        aliquota_multa=aliquota_multa,
        aliquota_juros_acumulada=aliquota_selic_acumulada,
    )


def calcular_denuncia_espontanea(
    valor: Decimal,
    data_vencimento: date,
    data_pagamento: date,
    taxas_selic: list[tuple[date, Decimal]],
) -> ResultadoMora:
    """Denúncia espontânea (CTN art. 138): sem multa, apenas SELIC + 1% mês.

    O contribuinte confessa e paga integralmente o débito antes de qualquer
    procedimento de ofício. A penalidade (multa) é excluída por força do
    CTN art. 138; os juros SELIC são mantidos por representarem correção
    monetária, não punição.

    Args:
        valor: Valor principal do tributo (NUNCA float).
        data_vencimento: Data de vencimento original.
        data_pagamento: Data do pagamento espontâneo.
        taxas_selic: Lista de (competencia_1o_dia, taxa_mensal).

    Returns:
        ResultadoMora com multa_mora e aliquota_multa sempre zero.
    """
    resultado = calcular_mora(valor, data_vencimento, data_pagamento, taxas_selic)
    # Exclui multa — CTN art. 138 afasta penalidade em denúncia espontânea
    total_sem_multa = resultado.juros_selic + resultado.acrescimo_mes_pagamento
    return ResultadoMora(
        valor_original=resultado.valor_original,
        multa_mora=Decimal("0"),
        juros_selic=resultado.juros_selic,
        acrescimo_mes_pagamento=resultado.acrescimo_mes_pagamento,
        total_acrescimos=total_sem_multa,
        valor_atualizado=resultado.valor_original + total_sem_multa,
        dias_atraso=resultado.dias_atraso,
        meses_selic=resultado.meses_selic,
        aliquota_multa=Decimal("0"),
        aliquota_juros_acumulada=resultado.aliquota_juros_acumulada,
    )


def primeiro_dia_mes_seguinte(d: date) -> date:
    """Retorna o 1º dia do mês seguinte a d."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)
