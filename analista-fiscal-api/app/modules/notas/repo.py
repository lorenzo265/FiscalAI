from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import DocumentoFiscal

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class NotasRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def criar_nfse(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        cnpj_emitente: str,
        focus_ref: str,
        numero_rps: str,
        valor_total: Decimal,
        status: str = "processando",
    ) -> DocumentoFiscal:
        """Cria registro imutável de NFS-e emitida (§8.2 — fatos fiscais imutáveis)."""
        doc = DocumentoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="nfse",
            direcao="saida",
            numero=numero_rps,
            serie="RPS",
            status=status,
            emitida_em=datetime.now(_TZ_BR),
            cnpj_emitente=cnpj_emitente,
            valor_total=valor_total,
            focus_ref=focus_ref,
            ingested_via="focus_nfe_emissao",
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def atualizar_status_nfse(
        self,
        *,
        focus_ref: str,
        status: str,
        numero: str | None = None,
        pdf_storage_key: str | None = None,
    ) -> DocumentoFiscal | None:
        """Atualiza status da NFS-e após callback do Focus NFe."""
        stmt = select(DocumentoFiscal).where(DocumentoFiscal.focus_ref == focus_ref)
        doc = (await self.session.execute(stmt)).scalar_one_or_none()
        if doc is None:
            return None
        doc.status = status
        if numero is not None:
            doc.numero = numero
        if pdf_storage_key is not None:
            doc.pdf_storage_key = pdf_storage_key
        await self.session.flush()
        return doc

    async def por_focus_ref(self, focus_ref: str) -> DocumentoFiscal | None:
        stmt = select(DocumentoFiscal).where(DocumentoFiscal.focus_ref == focus_ref)
        return (await self.session.execute(stmt)).scalar_one_or_none()
