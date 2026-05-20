"""Repositórios — parcelamentos (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ParcelaFiscal, ParcelamentoFiscal


class ParcelamentoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, parcelamento_id: UUID) -> ParcelamentoFiscal | None:
        stmt = select(ParcelamentoFiscal).where(
            ParcelamentoFiscal.id == parcelamento_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        status: str | None = None,
        limite: int = 50,
    ) -> list[ParcelamentoFiscal]:
        stmt = (
            select(ParcelamentoFiscal)
            .where(ParcelamentoFiscal.empresa_id == empresa_id)
            .order_by(ParcelamentoFiscal.data_adesao.desc())
            .limit(limite)
        )
        if status:
            stmt = stmt.where(ParcelamentoFiscal.status == status)
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(
        self, p: ParcelamentoFiscal, parcelas: list[ParcelaFiscal]
    ) -> ParcelamentoFiscal:
        self._s.add(p)
        await self._s.flush()
        for parcela in parcelas:
            parcela.parcelamento_id = p.id
        self._s.add_all(parcelas)
        await self._s.flush()
        await self._s.refresh(p)
        return p

    async def listar_parcelas(
        self, parcelamento_id: UUID
    ) -> list[ParcelaFiscal]:
        stmt = (
            select(ParcelaFiscal)
            .where(ParcelaFiscal.parcelamento_id == parcelamento_id)
            .order_by(ParcelaFiscal.numero)
        )
        return list((await self._s.execute(stmt)).scalars().all())
