from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def set_tenant_id(session: AsyncSession, tenant_id: UUID) -> None:
    """Aplica RLS na sessão atual via ``set_config(..., is_local := true)``.

    Equivalente a ``SET LOCAL app.tenant_id = '...'`` mas aceita bind parameter,
    eliminando interpolação de string em SQL. ``is_local=true`` faz o setting
    valer apenas para a transação corrente — mesmo escopo do ``SET LOCAL``.

    Princípio §8.1 do Plano: toda sessão SQLAlchemy entregue a endpoint/worker
    DEVE chamar este helper antes de qualquer query de domínio.
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def set_contador_id(session: AsyncSession, contador_id: UUID) -> None:
    """Aplica a GUC do parceiro marketplace via ``set_config(..., true)``.

    Espelha :func:`set_tenant_id` mas para a policy ``consulta_mkt_parceiro``
    (Sprint 13 / migration 0032). Junto com ``SET LOCAL ROLE marketplace_partner``
    libera o contador a enxergar suas consultas no fluxo de aceitar/responder.
    """
    await session.execute(
        text("SELECT set_config('app.contador_id', :cid, true)"),
        {"cid": str(contador_id)},
    )


@asynccontextmanager
async def session_with_tenant(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
) -> AsyncIterator[AsyncSession]:
    """Context manager para workers Celery — injeta RLS como get_session faz nos endpoints.

    Usage::

        async with session_with_tenant(session_factory, tenant_id) as session:
            ...
    """
    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE fiscal_app"))
        await set_tenant_id(session, tenant_id)
        yield session
