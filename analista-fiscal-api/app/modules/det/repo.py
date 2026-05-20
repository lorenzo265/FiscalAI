"""Repositório DET (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import MensagemDet


class MensagemDetRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar_por_id_externo(
        self, empresa_id: UUID, id_externo_det: str
    ) -> MensagemDet | None:
        stmt = select(MensagemDet).where(
            MensagemDet.empresa_id == empresa_id,
            MensagemDet.id_externo_det == id_externo_det,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        somente_nao_lidas: bool = False,
        limite: int = 100,
    ) -> list[MensagemDet]:
        stmt = (
            select(MensagemDet)
            .where(MensagemDet.empresa_id == empresa_id)
            .order_by(MensagemDet.recebida_em.desc())
            .limit(limite)
        )
        if somente_nao_lidas:
            stmt = stmt.where(MensagemDet.lida_em.is_(None))
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, m: MensagemDet) -> MensagemDet:
        self._s.add(m)
        await self._s.flush()
        await self._s.refresh(m)
        return m

    async def marcar_lida(
        self, mensagem: MensagemDet, em: datetime
    ) -> MensagemDet:
        mensagem.lida_em = em
        await self._s.flush()
        return mensagem
