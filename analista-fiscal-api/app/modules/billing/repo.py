"""Repositórios async do billing (Marco 2)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import Assinatura, EventoBilling, Fatura


class AssinaturaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar(self, a: Assinatura) -> Assinatura:
        self._s.add(a)
        await self._s.flush()
        return a

    async def ativa_do_tenant(self, tenant_id: UUID) -> Assinatura | None:
        """Assinatura viva (trial/ativa/inadimplente) do tenant, se houver."""
        stmt = (
            select(Assinatura)
            .where(
                Assinatura.tenant_id == tenant_id,
                Assinatura.status.in_(("trial", "ativa", "inadimplente")),
            )
            .order_by(Assinatura.criado_em.desc())
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def por_id(self, assinatura_id: UUID) -> Assinatura | None:
        return await self._s.get(Assinatura, assinatura_id)

    async def por_stripe_subscription(self, sub_id: str) -> Assinatura | None:
        stmt = select(Assinatura).where(
            Assinatura.stripe_subscription_id == sub_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


class FaturaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_stripe_invoice(self, invoice_id: str) -> Fatura | None:
        stmt = select(Fatura).where(Fatura.stripe_invoice_id == invoice_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(self, f: Fatura) -> Fatura:
        self._s.add(f)
        await self._s.flush()
        return f


class EventoBillingRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_stripe_event(self, event_id: str) -> EventoBilling | None:
        stmt = select(EventoBilling).where(
            EventoBilling.stripe_event_id == event_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(self, e: EventoBilling) -> EventoBilling:
        self._s.add(e)
        await self._s.flush()
        return e
