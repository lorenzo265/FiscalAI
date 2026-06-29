"""Repositório do módulo EFD-Reinf (Sprint 11 PR2)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import EfdReinfEvento


class EfdReinfRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar(
        self, empresa_id: UUID, tipo_evento: str, referencia_id: UUID
    ) -> EfdReinfEvento | None:
        stmt = select(EfdReinfEvento).where(
            EfdReinfEvento.empresa_id == empresa_id,
            EfdReinfEvento.tipo_evento == tipo_evento,
            EfdReinfEvento.referencia_id == referencia_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_empresa(
        self,
        empresa_id: UUID,
        *,
        tipo_evento: str | None = None,
        periodo: date | None = None,
        limite: int = 100,
    ) -> list[EfdReinfEvento]:
        stmt = (
            select(EfdReinfEvento)
            .where(EfdReinfEvento.empresa_id == empresa_id)
            .order_by(EfdReinfEvento.criado_em.desc())
            .limit(limite)
        )
        if tipo_evento:
            stmt = stmt.where(EfdReinfEvento.tipo_evento == tipo_evento)
        if periodo:
            stmt = stmt.where(EfdReinfEvento.periodo_apuracao == periodo)
        return list((await self._s.execute(stmt)).scalars().all())

    async def por_id(self, evento_id: UUID) -> EfdReinfEvento | None:
        stmt = select(EfdReinfEvento).where(EfdReinfEvento.id == evento_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_por_status(
        self,
        empresa_id: UUID,
        *,
        status: str,
        limite: int = 200,
    ) -> list[EfdReinfEvento]:
        stmt = (
            select(EfdReinfEvento)
            .where(EfdReinfEvento.empresa_id == empresa_id)
            .where(EfdReinfEvento.status == status)
            .order_by(EfdReinfEvento.criado_em.asc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_por_lote(
        self, lote_protocolo: str
    ) -> list[EfdReinfEvento]:
        stmt = (
            select(EfdReinfEvento)
            .where(EfdReinfEvento.lote_protocolo == lote_protocolo)
            .order_by(EfdReinfEvento.criado_em.asc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, e: EfdReinfEvento) -> EfdReinfEvento:
        self._s.add(e)
        await self._s.flush()
        await self._s.refresh(e)
        return e
