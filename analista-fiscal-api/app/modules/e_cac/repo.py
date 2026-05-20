"""Repositório de mensagens e-CAC."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import MensagemECac


class MensagensECacRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert_recebida(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        id_externo_serpro: str,
        assunto: str,
        corpo: str | None,
        recebida_em: datetime,
        origem: str = "RFB",
    ) -> bool:
        """Insere se nova, no-op se já existir (ON CONFLICT na UNIQUE).

        Retorna True se a linha foi efetivamente inserida.
        """
        stmt = (
            pg_insert(MensagemECac)
            .values(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                id_externo_serpro=id_externo_serpro,
                assunto=assunto[:255],
                corpo=corpo,
                origem=origem,
                recebida_em=recebida_em,
            )
            .on_conflict_do_nothing(constraint="uq_mensagem_e_cac_idempotente")
            .returning(MensagemECac.id)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def aplicar_classificacao(
        self,
        mensagem_id: UUID,
        *,
        tipo: str,
        prioridade: str,
        classificador_versao: str,
        prazo_resposta: date | None = None,
        encaminhada_marketplace: bool = False,
    ) -> None:
        m = await self.por_id(mensagem_id)
        if m is None:
            return
        m.tipo = tipo
        m.prioridade = prioridade
        m.classificada_em = datetime.now(tz=None)
        m.classificador_versao = classificador_versao
        m.prazo_resposta = prazo_resposta
        m.encaminhada_marketplace = encaminhada_marketplace
        await self._s.flush()

    async def nao_classificadas(self, empresa_id: UUID) -> list[MensagemECac]:
        stmt = (
            select(MensagemECac)
            .where(
                MensagemECac.empresa_id == empresa_id,
                MensagemECac.classificada_em.is_(None),
            )
            .order_by(desc(MensagemECac.recebida_em))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar(self, empresa_id: UUID) -> list[MensagemECac]:
        stmt = (
            select(MensagemECac)
            .where(MensagemECac.empresa_id == empresa_id)
            .order_by(desc(MensagemECac.recebida_em))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def por_id(self, mensagem_id: UUID) -> MensagemECac | None:
        stmt = select(MensagemECac).where(MensagemECac.id == mensagem_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()
