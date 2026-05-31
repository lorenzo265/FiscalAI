"""Repositórios — lote de importação + arquivo SPED (Sprint 18 PR2).

``ArquivoSpedRepo`` da Sprint 16 PR1 já cobre persistência do arquivo;
aqui apenas adicionamos o ``LoteImportacaoRepo`` específico do bounded
context ``migracao``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import LoteImportacao
from app.shared.types import JsonObject

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class LoteImportacaoRepo:
    """Acesso a ``lote_importacao`` (Sprint 18 PR1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, lote_id: UUID) -> LoteImportacao | None:
        stmt = select(LoteImportacao).where(LoteImportacao.id == lote_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_hash_concluido(
        self, empresa_id: UUID, hash_arquivo: str
    ) -> LoteImportacao | None:
        """Idempotência §8.9: re-upload do mesmo arquivo devolve lote anterior.

        Usa o UNIQUE parcial ``uq_lote_empresa_hash_concluido`` da migration
        0040 (``status='concluido'``) — apenas lotes que terminaram com
        sucesso atrapalham reprocessamento; lotes ``falhou`` permitem
        retry.
        """
        stmt = (
            select(LoteImportacao)
            .where(
                LoteImportacao.empresa_id == empresa_id,
                LoteImportacao.hash_arquivo == hash_arquivo,
                LoteImportacao.status == "concluido",
            )
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_empresa(
        self, empresa_id: UUID, *, limite: int = 50
    ) -> list[LoteImportacao]:
        stmt = (
            select(LoteImportacao)
            .where(LoteImportacao.empresa_id == empresa_id)
            .order_by(desc(LoteImportacao.iniciado_em))
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        fonte: str,
        arquivo_sped_id: UUID | None,
        nome_arquivo: str | None,
        hash_arquivo: str,
        algoritmo_versao: str,
    ) -> LoteImportacao:
        lote = LoteImportacao(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            fonte=fonte,
            arquivo_sped_id=arquivo_sped_id,
            nome_arquivo=nome_arquivo,
            hash_arquivo=hash_arquivo,
            algoritmo_versao=algoritmo_versao,
            status="processando",
        )
        self._s.add(lote)
        await self._s.flush()
        return lote

    async def concluir(
        self,
        lote_id: UUID,
        *,
        resumo: JsonObject,
        erros: JsonObject | None = None,
    ) -> None:
        """Marca lote como concluído (status final + concluido_em + jsonbs)."""
        await self._s.execute(
            update(LoteImportacao)
            .where(LoteImportacao.id == lote_id)
            .values(
                status="concluido",
                concluido_em=datetime.now(_TZ_BR),
                resumo_jsonb=resumo,
                erros_jsonb=erros,
            )
        )

    async def marcar_falhou(
        self, lote_id: UUID, *, erros: JsonObject
    ) -> None:
        """Marca lote como falhou — preserva o que foi processado para audit."""
        await self._s.execute(
            update(LoteImportacao)
            .where(LoteImportacao.id == lote_id)
            .values(
                status="falhou",
                concluido_em=datetime.now(_TZ_BR),
                erros_jsonb=erros,
            )
        )
