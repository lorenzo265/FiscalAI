from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import AgendaItem, Empresa


async def buscar_regime_empresa(session: AsyncSession, empresa_id: UUID) -> str:
    stmt = select(Empresa.regime_tributario).where(Empresa.id == empresa_id)
    result = await session.execute(stmt)
    regime = result.scalar_one_or_none()
    if regime is None:
        raise ValueError(f"Empresa {empresa_id} não encontrada")
    return regime


async def listar_agenda(
    session: AsyncSession,
    empresa_id: UUID,
    ano: int | None = None,
) -> list[AgendaItem]:
    stmt = select(AgendaItem).where(AgendaItem.empresa_id == empresa_id)
    if ano is not None:
        stmt = stmt.where(
            AgendaItem.data_vencimento >= date(ano, 1, 1),
            AgendaItem.data_vencimento <= date(ano, 12, 31),
        )
    stmt = stmt.order_by(AgendaItem.data_vencimento)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def deletar_agenda_ano(
    session: AsyncSession,
    empresa_id: UUID,
    ano: int,
) -> None:
    stmt = delete(AgendaItem).where(
        AgendaItem.empresa_id == empresa_id,
        AgendaItem.data_vencimento >= date(ano, 1, 1),
        AgendaItem.data_vencimento <= date(ano + 1, 12, 31),
    )
    await session.execute(stmt)


async def salvar_itens(
    session: AsyncSession,
    itens: list[AgendaItem],
) -> None:
    session.add_all(itens)
    await session.flush()
