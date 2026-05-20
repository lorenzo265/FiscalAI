from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import SessaoWhatsApp


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
