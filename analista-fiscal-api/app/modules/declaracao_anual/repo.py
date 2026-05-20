"""Repositório de declarações anuais."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import DeclaracaoAnual
from app.shared.types import JsonObject


class DeclaracaoAnualRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar(
        self, empresa_id: UUID, tipo: str, ano_base: int
    ) -> DeclaracaoAnual | None:
        stmt = select(DeclaracaoAnual).where(
            DeclaracaoAnual.empresa_id == empresa_id,
            DeclaracaoAnual.tipo == tipo,
            DeclaracaoAnual.ano_base == ano_base,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        tipo: str,
        ano_base: int,
        payload_json: JsonObject,
        algoritmo_versao: str,
        idempotency_key: str,
    ) -> DeclaracaoAnual:
        decl = DeclaracaoAnual(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=tipo,
            ano_base=ano_base,
            status="gerada",
            payload_json=payload_json,
            algoritmo_versao=algoritmo_versao,
            idempotency_key=idempotency_key,
        )
        self._s.add(decl)
        await self._s.flush()
        return decl

    async def marcar_transmitida(
        self,
        decl_id: UUID,
        *,
        protocolo: str | None,
        recibo_pdf_storage_key: str | None,
    ) -> None:
        decl = await self.por_id(decl_id)
        if decl is None:
            return
        decl.status = "transmitida"
        decl.protocolo = protocolo
        decl.recibo_pdf_storage_key = recibo_pdf_storage_key
        decl.transmitida_em = datetime.now(tz=None)
        await self._s.flush()

    async def marcar_erro(
        self, decl_id: UUID, *, erro_codigo: str, erro_mensagem: str
    ) -> None:
        decl = await self.por_id(decl_id)
        if decl is None:
            return
        decl.status = "erro"
        decl.erro_codigo = erro_codigo
        decl.erro_mensagem = erro_mensagem
        await self._s.flush()

    async def por_id(self, decl_id: UUID) -> DeclaracaoAnual | None:
        stmt = select(DeclaracaoAnual).where(DeclaracaoAnual.id == decl_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(self, empresa_id: UUID) -> list[DeclaracaoAnual]:
        stmt = (
            select(DeclaracaoAnual)
            .where(DeclaracaoAnual.empresa_id == empresa_id)
            .order_by(desc(DeclaracaoAnual.ano_base), desc(DeclaracaoAnual.criado_em))
        )
        return list((await self._s.execute(stmt)).scalars().all())
