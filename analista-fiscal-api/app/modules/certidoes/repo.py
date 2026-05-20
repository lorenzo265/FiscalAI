"""Repositório de certidões — append-only sob RLS."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.types import JsonObject

from app.shared.db.models import Certidao


class CertidoesRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        tipo: str,
        status: str,
        emitida_em: datetime,
        numero: str | None = None,
        valid_until: date | None = None,
        pdf_storage_key: str | None = None,
        payload_json: JsonObject | None = None,
        serpro_chamada_id: UUID | None = None,
    ) -> Certidao:
        certidao = Certidao(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=tipo,
            numero=numero,
            status=status,
            emitida_em=emitida_em,
            valid_until=valid_until,
            pdf_storage_key=pdf_storage_key,
            payload_json=payload_json,
            serpro_chamada_id=serpro_chamada_id,
        )
        self._s.add(certidao)
        await self._s.flush()
        return certidao

    async def vigente(
        self, empresa_id: UUID, tipo: str, *, hoje: date | None = None
    ) -> Certidao | None:
        """Retorna a certidão vigente (valid_until >= hoje) mais recente, se houver."""
        hoje = hoje or date.today()
        stmt = (
            select(Certidao)
            .where(
                Certidao.empresa_id == empresa_id,
                Certidao.tipo == tipo,
                Certidao.valid_until >= hoje,
                Certidao.status.in_(
                    [
                        "negativa",
                        "positiva_com_efeitos_de_negativa",
                        "emitida",
                    ]
                ),
            )
            .order_by(desc(Certidao.emitida_em))
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(self, empresa_id: UUID) -> list[Certidao]:
        stmt = (
            select(Certidao)
            .where(Certidao.empresa_id == empresa_id)
            .order_by(desc(Certidao.emitida_em))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def por_id(self, certidao_id: UUID) -> Certidao | None:
        stmt = select(Certidao).where(Certidao.id == certidao_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()
