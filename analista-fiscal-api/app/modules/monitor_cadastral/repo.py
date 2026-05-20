"""Repositório — monitor cadastral RFB + Sintegra (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import StatusCadastralRfb, StatusSintegra


class StatusRfbRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def mais_recente(self, empresa_id: UUID) -> StatusCadastralRfb | None:
        stmt = (
            select(StatusCadastralRfb)
            .where(StatusCadastralRfb.empresa_id == empresa_id)
            .order_by(StatusCadastralRfb.consultado_em.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def historico(
        self, empresa_id: UUID, *, limite: int = 50
    ) -> list[StatusCadastralRfb]:
        stmt = (
            select(StatusCadastralRfb)
            .where(StatusCadastralRfb.empresa_id == empresa_id)
            .order_by(StatusCadastralRfb.consultado_em.desc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, s: StatusCadastralRfb) -> StatusCadastralRfb:
        self._s.add(s)
        await self._s.flush()
        await self._s.refresh(s)
        return s


class StatusSintegraRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def mais_recente_por_uf(
        self, empresa_id: UUID, uf: str
    ) -> StatusSintegra | None:
        stmt = (
            select(StatusSintegra)
            .where(StatusSintegra.empresa_id == empresa_id)
            .where(StatusSintegra.uf == uf)
            .order_by(StatusSintegra.consultado_em.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def historico(
        self,
        empresa_id: UUID,
        *,
        uf: str | None = None,
        limite: int = 50,
    ) -> list[StatusSintegra]:
        stmt = (
            select(StatusSintegra)
            .where(StatusSintegra.empresa_id == empresa_id)
            .order_by(StatusSintegra.consultado_em.desc())
            .limit(limite)
        )
        if uf:
            stmt = stmt.where(StatusSintegra.uf == uf)
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, s: StatusSintegra) -> StatusSintegra:
        self._s.add(s)
        await self._s.flush()
        await self._s.refresh(s)
        return s
