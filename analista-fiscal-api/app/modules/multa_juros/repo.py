from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import SelicMensal


async def buscar_taxas_selic(
    session: AsyncSession,
    data_inicio: date,
    data_fim: date,
) -> list[tuple[date, Decimal]]:
    """Retorna [(competencia, taxa_mensal)] no intervalo [data_inicio, data_fim]."""
    stmt = (
        select(SelicMensal.competencia, SelicMensal.taxa_mensal)
        .where(SelicMensal.competencia >= data_inicio)
        .where(SelicMensal.competencia <= data_fim)
        .order_by(SelicMensal.competencia)
    )
    result = await session.execute(stmt)
    return [(row.competencia, row.taxa_mensal) for row in result]
