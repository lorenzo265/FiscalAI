"""Repositório de items Pluggy."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import PluggyItem


class PluggyItemRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_pluggy_id(self, pluggy_item_id: str) -> PluggyItem | None:
        stmt = select(PluggyItem).where(PluggyItem.pluggy_item_id == pluggy_item_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_id(self, item_uuid: UUID) -> PluggyItem | None:
        stmt = select(PluggyItem).where(PluggyItem.id == item_uuid)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        pluggy_item_id: str,
        connector_id: int | None,
        connector_nome: str | None,
        status: str,
        status_detalhe: str | None = None,
    ) -> PluggyItem:
        item = PluggyItem(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            pluggy_item_id=pluggy_item_id,
            connector_id=connector_id,
            connector_nome=connector_nome,
            status=status,
            status_detalhe=status_detalhe,
        )
        self._s.add(item)
        await self._s.flush()
        return item

    async def atualizar_status(
        self,
        item_uuid: UUID,
        *,
        status: str,
        status_detalhe: str | None = None,
        last_sync_at: datetime | None = None,
        erro_codigo: str | None = None,
    ) -> None:
        item = await self.por_id(item_uuid)
        if item is None:
            return
        item.status = status
        if status_detalhe is not None:
            item.status_detalhe = status_detalhe
        if last_sync_at is not None:
            item.last_sync_at = last_sync_at
        if erro_codigo is not None:
            item.erro_codigo = erro_codigo
        await self._s.flush()

    async def listar(self, empresa_id: UUID) -> list[PluggyItem]:
        stmt = (
            select(PluggyItem)
            .where(PluggyItem.empresa_id == empresa_id, PluggyItem.ativo.is_(True))
            .order_by(desc(PluggyItem.criado_em))
        )
        return list((await self._s.execute(stmt)).scalars().all())
