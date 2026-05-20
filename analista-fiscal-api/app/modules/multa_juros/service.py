from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.multa_juros.calcula_selic import (
    ResultadoMora,
    calcular_denuncia_espontanea,
    calcular_mora,
    primeiro_dia_mes_seguinte,
)
from app.modules.multa_juros.repo import buscar_taxas_selic
from app.modules.multa_juros.schemas import SimularMoraIn, SimularMoraOut
from app.shared.exceptions import DomainError


class SelicInsuficienteError(DomainError):
    http_status = 422

    def __init__(self, competencia: date) -> None:
        super().__init__(
            mensagem=f"Taxa SELIC não disponível para competência {competencia}. "
            "Solicite atualização da tabela SELIC ao administrador.",
            codigo="SELIC_INSUFICIENTE",
        )


def _resultado_para_out(resultado: ResultadoMora, payload: SimularMoraIn) -> SimularMoraOut:
    return SimularMoraOut(
        valor_original=resultado.valor_original,
        multa_mora=resultado.multa_mora,
        juros_selic=resultado.juros_selic,
        acrescimo_mes_pagamento=resultado.acrescimo_mes_pagamento,
        total_acrescimos=resultado.total_acrescimos,
        valor_atualizado=resultado.valor_atualizado,
        dias_atraso=resultado.dias_atraso,
        meses_selic=resultado.meses_selic,
        aliquota_multa=resultado.aliquota_multa,
        aliquota_juros_acumulada=resultado.aliquota_juros_acumulada,
        data_vencimento=payload.data_vencimento,
        data_pagamento=payload.data_pagamento,
    )


async def _buscar_taxas(payload: SimularMoraIn, session: AsyncSession) -> list[tuple[date, Decimal]]:
    data_inicio = primeiro_dia_mes_seguinte(payload.data_vencimento)
    data_fim = date(payload.data_pagamento.year, payload.data_pagamento.month, 1)
    return await buscar_taxas_selic(session, data_inicio, data_fim)


async def simular_mora(
    payload: SimularMoraIn,
    session: AsyncSession,
) -> SimularMoraOut:
    """Mora ordinária: multa 0,33%/dia (teto 20%) + SELIC + 1% mês (Lei 9.430/1996, art. 61)."""
    taxas = await _buscar_taxas(payload, session)
    try:
        resultado = calcular_mora(
            valor=payload.valor,
            data_vencimento=payload.data_vencimento,
            data_pagamento=payload.data_pagamento,
            taxas_selic=taxas,
        )
    except ValueError as exc:
        raise SelicInsuficienteError(primeiro_dia_mes_seguinte(payload.data_vencimento)) from exc
    return _resultado_para_out(resultado, payload)


async def simular_denuncia_espontanea(
    payload: SimularMoraIn,
    session: AsyncSession,
) -> SimularMoraOut:
    """Denúncia espontânea (CTN art. 138): sem multa — apenas SELIC + 1% mês."""
    taxas = await _buscar_taxas(payload, session)
    try:
        resultado = calcular_denuncia_espontanea(
            valor=payload.valor,
            data_vencimento=payload.data_vencimento,
            data_pagamento=payload.data_pagamento,
            taxas_selic=taxas,
        )
    except ValueError as exc:
        raise SelicInsuficienteError(primeiro_dia_mes_seguinte(payload.data_vencimento)) from exc
    return _resultado_para_out(resultado, payload)


async def calcular_mora_valor(
    valor: Decimal,
    data_vencimento: date,
    data_pagamento: date,
    session: AsyncSession,
) -> ResultadoMora:
    """Helper para chamadas internas (ex.: assistente, apuração)."""
    payload = SimularMoraIn(
        valor=valor,
        data_vencimento=data_vencimento,
        data_pagamento=data_pagamento,
    )
    out = await simular_mora(payload, session)
    return ResultadoMora(
        valor_original=out.valor_original,
        multa_mora=out.multa_mora,
        juros_selic=out.juros_selic,
        acrescimo_mes_pagamento=out.acrescimo_mes_pagamento,
        total_acrescimos=out.total_acrescimos,
        valor_atualizado=out.valor_atualizado,
        dias_atraso=out.dias_atraso,
        meses_selic=out.meses_selic,
        aliquota_multa=out.aliquota_multa,
        aliquota_juros_acumulada=out.aliquota_juros_acumulada,
    )
