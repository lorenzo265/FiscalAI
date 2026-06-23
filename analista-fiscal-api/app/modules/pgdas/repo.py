"""Repositório de transmissões PGDAS-D."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import TransmissaoPgdas
from app.shared.types import JsonObject


class TransmissoesPgdasRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        apuracao_id: UUID,
        competencia: date,
        tentativa: int,
        eh_retificadora: bool,
        idempotency_key: str,
        status: str = "pendente",
        payload_envio_json: JsonObject | None = None,
    ) -> TransmissaoPgdas:
        tr = TransmissaoPgdas(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            apuracao_id=apuracao_id,
            competencia=competencia,
            tentativa=tentativa,
            eh_retificadora=eh_retificadora,
            idempotency_key=idempotency_key,
            status=status,
            payload_envio_json=payload_envio_json,
        )
        self._s.add(tr)
        await self._s.flush()
        return tr

    async def marcar_sucesso(
        self,
        transmissao_id: UUID,
        *,
        protocolo: str | None,
        resposta_json: JsonObject | None,
        recibo_pdf_storage_key: str | None = None,
    ) -> None:
        tr = await self.por_id(transmissao_id)
        if tr is None:
            return
        tr.status = "transmitida"
        tr.protocolo = protocolo
        tr.resposta_json = resposta_json
        tr.recibo_pdf_storage_key = recibo_pdf_storage_key
        await self._s.flush()

    async def marcar_erro(
        self,
        transmissao_id: UUID,
        *,
        erro_codigo: str,
        erro_mensagem: str,
        resposta_json: JsonObject | None = None,
    ) -> None:
        tr = await self.por_id(transmissao_id)
        if tr is None:
            return
        tr.status = "erro"
        tr.erro_codigo = erro_codigo
        tr.erro_mensagem = erro_mensagem
        tr.resposta_json = resposta_json
        await self._s.flush()

    async def por_id(self, transmissao_id: UUID) -> TransmissaoPgdas | None:
        stmt = select(TransmissaoPgdas).where(TransmissaoPgdas.id == transmissao_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def ultima_transmissao(
        self, empresa_id: UUID, competencia: date
    ) -> TransmissaoPgdas | None:
        stmt = (
            select(TransmissaoPgdas)
            .where(
                TransmissaoPgdas.empresa_id == empresa_id,
                TransmissaoPgdas.competencia == competencia,
            )
            .order_by(desc(TransmissaoPgdas.tentativa))
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def proxima_tentativa(self, empresa_id: UUID, competencia: date) -> int:
        stmt = select(func.coalesce(func.max(TransmissaoPgdas.tentativa), 0)).where(
            TransmissaoPgdas.empresa_id == empresa_id,
            TransmissaoPgdas.competencia == competencia,
        )
        n = int((await self._s.execute(stmt)).scalar_one() or 0)
        return n + 1

    async def listar(
        self, empresa_id: UUID, *, competencia: date | None = None
    ) -> list[TransmissaoPgdas]:
        stmt = select(TransmissaoPgdas).where(TransmissaoPgdas.empresa_id == empresa_id)
        if competencia is not None:
            stmt = stmt.where(TransmissaoPgdas.competencia == competencia)
        stmt = stmt.order_by(desc(TransmissaoPgdas.criado_em))
        return list((await self._s.execute(stmt)).scalars().all())
