from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.shared.auth.jwt import TenantContext, verificar_token
from app.shared.db.rls import set_tenant_id
from app.shared.exceptions import TokenInvalido

_bearer = HTTPBearer(auto_error=False)


async def get_tenant_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TenantContext:
    """Extrai e valida o JWT do header Authorization: Bearer <token>."""
    if credentials is None:
        raise TokenInvalido("Autenticação necessária")
    return verificar_token(credentials.credentials)


async def get_anon_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Sessão sem contexto de tenant — usar APENAS em endpoints de auth (register/login).

    Usa SET LOCAL ROLE fiscal_app para que o RLS seja aplicado mesmo com a conexão
    sendo feita pelo superuser fiscal (superusers bypassam RLS sem o SET ROLE).
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE fiscal_app"))
        yield session


async def get_session(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Sessão com RLS ativo via SET LOCAL — padrão para todos os endpoints autenticados."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE fiscal_app"))
        await set_tenant_id(session, ctx.tenant_id)
        yield session


# Aliases Annotated para endpoints (reduz verbosidade)
TenantDep = Annotated[TenantContext, Depends(get_tenant_context)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
AnonSessionDep = Annotated[AsyncSession, Depends(get_anon_session)]
