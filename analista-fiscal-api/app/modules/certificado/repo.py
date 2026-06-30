"""Repositório — cofre de certificado A1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.shared.db.models import CertificadoA1


class CertificadoA1Repo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def obter_ativo(self, empresa_id: UUID) -> CertificadoA1 | None:
        """O certificado ativo da empresa (RLS garante isolamento)."""
        stmt = select(CertificadoA1).where(
            CertificadoA1.empresa_id == empresa_id,
            CertificadoA1.ativo.is_(True),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def desativar_ativos(self, empresa_id: UUID) -> None:
        """Desativa o(s) certificado(s) ativo(s) da empresa (substituição)."""
        stmt = (
            update(CertificadoA1)
            .where(
                CertificadoA1.empresa_id == empresa_id,
                CertificadoA1.ativo.is_(True),
            )
            .values(ativo=False, atualizado_em=func.now())
        )
        await self._s.execute(stmt)

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        pfx_cifrado: str,
        senha_cifrada: str,
        cn_titular: str,
        cnpj_titular: str | None,
        validade_inicio: datetime,
        validade_fim: datetime,
        fingerprint: str,
    ) -> CertificadoA1:
        """Persiste um novo certificado ativo."""
        obj = CertificadoA1(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            pfx_cifrado=pfx_cifrado,
            senha_cifrada=senha_cifrada,
            cn_titular=cn_titular,
            cnpj_titular=cnpj_titular,
            validade_inicio=validade_inicio,
            validade_fim=validade_fim,
            fingerprint=fingerprint,
            ativo=True,
        )
        self._s.add(obj)
        await self._s.flush()
        return obj
