from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import SessaoWhatsApp, WhatsappMensagemProcessada


class MensagemProcessadaRepo:
    """Dedup de mensagens do webhook Meta WhatsApp (§8.9 — Fase 2 PR7)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def marcar_processada(
        self,
        *,
        mensagem_id: str,
        tenant_id: UUID,
        empresa_id: UUID,
        phone: str,
    ) -> bool:
        """Registra a mensagem como processada de forma atômica.

        Returns:
            ``True`` se a mensagem foi registrada agora (primeira vez vista),
            ``False`` se já existia (retry do Meta — caller deve ignorar).
        """
        stmt = (
            pg_insert(WhatsappMensagemProcessada)
            .values(
                mensagem_id=mensagem_id,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                phone=phone,
            )
            .on_conflict_do_nothing(index_elements=["mensagem_id"])
        )
        result = await self.session.execute(stmt)
        # rowcount == 1 quando INSERT efetivou; 0 quando ON CONFLICT disparou.
        rowcount = int(getattr(result, "rowcount", 0) or 0)
        return rowcount > 0


class SessaoWhatsAppRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def obter_ou_criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        phone: str,
    ) -> SessaoWhatsApp:
        """Retorna sessão existente ou cria uma nova."""
        stmt = select(SessaoWhatsApp).where(
            SessaoWhatsApp.tenant_id == tenant_id,
            SessaoWhatsApp.phone == phone,
        )
        sessao = (await self.session.execute(stmt)).scalar_one_or_none()
        if sessao is None:
            sessao = SessaoWhatsApp(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                phone=phone,
            )
            self.session.add(sessao)
            await self.session.flush()
        return sessao

    async def incrementar_mensagens(self, sessao: SessaoWhatsApp) -> None:
        import datetime
        from zoneinfo import ZoneInfo

        sessao.mensagens_na_sessao += 1
        sessao.updated_at = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
        await self.session.flush()

    async def por_phone(self, tenant_id: UUID, phone: str) -> SessaoWhatsApp | None:
        stmt = select(SessaoWhatsApp).where(
            SessaoWhatsApp.tenant_id == tenant_id,
            SessaoWhatsApp.phone == phone,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
