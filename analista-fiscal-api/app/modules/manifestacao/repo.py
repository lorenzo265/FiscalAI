"""Repositório — Manifestação do Destinatário NF-e (MD-e)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ManifestacaoNFe


class ManifestacaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, manifestacao_id: UUID) -> ManifestacaoNFe | None:
        """Busca por PK (RLS garante cross-tenant isolation)."""
        stmt = select(ManifestacaoNFe).where(ManifestacaoNFe.id == manifestacao_id)
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def por_idempotency_key(
        self, empresa_id: UUID, idempotency_key: str
    ) -> ManifestacaoNFe | None:
        """Busca por chave de idempotência scoped à empresa."""
        stmt = select(ManifestacaoNFe).where(
            ManifestacaoNFe.empresa_id == empresa_id,
            ManifestacaoNFe.idempotency_key == idempotency_key,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def por_chave_tipo_seq(
        self,
        empresa_id: UUID,
        chave_nfe: str,
        tipo_evento: str,
        sequencial: int,
    ) -> ManifestacaoNFe | None:
        """Busca pelo UNIQUE natural (empresa, chave, tipo, seq)."""
        stmt = select(ManifestacaoNFe).where(
            ManifestacaoNFe.empresa_id == empresa_id,
            ManifestacaoNFe.chave_nfe == chave_nfe,
            ManifestacaoNFe.tipo_evento == tipo_evento,
            ManifestacaoNFe.sequencial == sequencial,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def listar_empresa(
        self,
        empresa_id: UUID,
        *,
        chave_nfe: str | None = None,
        tipo_evento: str | None = None,
        status: str | None = None,
        limite: int = 100,
    ) -> list[ManifestacaoNFe]:
        """Lista manifestações de uma empresa, com filtros opcionais."""
        stmt = (
            select(ManifestacaoNFe)
            .where(ManifestacaoNFe.empresa_id == empresa_id)
            .order_by(ManifestacaoNFe.criado_em.desc())
            .limit(limite)
        )
        if chave_nfe is not None:
            stmt = stmt.where(ManifestacaoNFe.chave_nfe == chave_nfe)
        if tipo_evento is not None:
            stmt = stmt.where(ManifestacaoNFe.tipo_evento == tipo_evento)
        if status is not None:
            stmt = stmt.where(ManifestacaoNFe.status == status)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        chave_nfe: str,
        cnpj_destinatario: str,
        tipo_evento: str,
        sequencial: int,
        justificativa: str | None,
        status: str,
        algoritmo_versao: str,
        xml_evento_storage_key: str | None = None,
        idempotency_key: str | None = None,
        assinado_em: datetime | None = None,
    ) -> ManifestacaoNFe:
        """Persiste uma nova manifestação (append-only §8.2)."""
        obj = ManifestacaoNFe(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            chave_nfe=chave_nfe,
            cnpj_destinatario=cnpj_destinatario,
            tipo_evento=tipo_evento,
            sequencial=sequencial,
            justificativa=justificativa,
            status=status,
            algoritmo_versao=algoritmo_versao,
            xml_evento_storage_key=xml_evento_storage_key,
            idempotency_key=idempotency_key,
            assinado_em=assinado_em,
        )
        self._s.add(obj)
        await self._s.flush()
        return obj

    async def atualizar_status(
        self,
        obj: ManifestacaoNFe,
        *,
        status: str,
        assinado_em: datetime | None = None,
        xml_evento_storage_key: str | None = None,
    ) -> ManifestacaoNFe:
        """Atualiza metadados operacionais (não-fiscais) pós-assinatura.

        §8.2: só campos operacionais (status, storage_key, timestamps de
        ciclo de vida). O XML gerado em ``xml_evento_storage_key`` é imutável
        após gravação; não há UPDATE em campo fiscal.
        """
        obj.status = status
        if assinado_em is not None:
            obj.assinado_em = assinado_em
        if xml_evento_storage_key is not None:
            obj.xml_evento_storage_key = xml_evento_storage_key
        await self._s.flush()
        return obj
