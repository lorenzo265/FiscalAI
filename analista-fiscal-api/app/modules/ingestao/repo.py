from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import DocumentoFiscal


class DocumentoFiscalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buscar_por_chave(self, chave: str) -> DocumentoFiscal | None:
        stmt = select(DocumentoFiscal).where(DocumentoFiscal.chave == chave)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def listar_empresa(
        self,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        direcao: str | None = None,
        limit: int = 50,
    ) -> list[DocumentoFiscal]:
        stmt = (
            select(DocumentoFiscal)
            .where(DocumentoFiscal.empresa_id == empresa_id)
            .order_by(DocumentoFiscal.emitida_em.desc())
            .limit(limit)
        )
        if tipo:
            stmt = stmt.where(DocumentoFiscal.tipo == tipo)
        if direcao:
            stmt = stmt.where(DocumentoFiscal.direcao == direcao)
        return list((await self.session.execute(stmt)).scalars().all())

    async def salvar(self, doc: DocumentoFiscal) -> DocumentoFiscal:
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc
