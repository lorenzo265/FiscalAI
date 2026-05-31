from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.shared.auth.jwt import (
    ParceiroContext,
    TenantContext,
    verificar_token,
    verificar_token_parceiro,
)
from app.shared.db.rls import set_contador_id, set_tenant_id
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


# ── Contexto e sessão do contador parceiro (Sprint 13 PR3) ──────────────────


async def get_parceiro_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> ParceiroContext:
    """Extrai e valida o JWT de parceiro (typ='parceiro' obrigatório)."""
    if credentials is None:
        raise TokenInvalido("Autenticação necessária")
    return verificar_token_parceiro(credentials.credentials)


async def get_parceiro_session(
    ctx: Annotated[ParceiroContext, Depends(get_parceiro_context)],
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Sessão com role ``marketplace_partner`` + GUC ``app.contador_id``.

    Sprint 13 PR3 — habilita a policy ``consulta_mkt_parceiro`` da
    migration 0032. Cliente PME usa :func:`get_session` (RLS por tenant);
    parceiro usa esta — não compartilham GUC nem role.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE marketplace_partner"))
        await set_contador_id(session, ctx.contador_id)
        yield session


ParceiroDep = Annotated[ParceiroContext, Depends(get_parceiro_context)]
ParceiroSessionDep = Annotated[AsyncSession, Depends(get_parceiro_session)]


async def get_webhook_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Sessão para webhooks externos (provider de pagamento, Pluggy etc.).

    NÃO faz ``SET LOCAL ROLE fiscal_app`` — conexão usa o role superuser do
    ``DATABASE_URL`` (``fiscal``), que **bypassa RLS** em tabelas SEM
    ``FORCE ROW LEVEL SECURITY``. Use só em endpoints de sistema com
    autenticação própria (HMAC do provider). Sprint 13 PR3 — pagamento stub.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


WebhookSessionDep = Annotated[AsyncSession, Depends(get_webhook_session)]


# ── Painel admin de tabelas tributárias (Sprint 19.5 PR1) ────────────────────


async def require_tax_table_admin_token(
    request: Request,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    """Guard do painel admin de tabelas tributárias (Sprint 19.5 PR1).

    Reusa o mesmo ``settings.MARKETPLACE_ADMIN_TOKEN`` do marketplace
    (Sprint 13 PR1) — ambos endpoints são de sistema cross-tenant. Comparação
    em tempo constante via ``hmac.compare_digest``.

    Token vazio em settings → 503 (fail-closed: pre-prod sem token configurado
    nunca aceita POST). Token inválido → 401.
    """
    settings: Settings = request.app.state.settings
    expected = settings.MARKETPLACE_ADMIN_TOKEN
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "Endpoints administrativos de tabelas tributárias desabilitados "
                "(MARKETPLACE_ADMIN_TOKEN não configurado)."
            ),
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="X-Admin-Token inválido")


async def get_tax_table_admin_session(
    _admin: Annotated[None, Depends(require_tax_table_admin_token)],
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Sessão admin com ``SET LOCAL ROLE tax_table_admin``.

    Sprint 19.5 PR1. **Não seta** ``app.tenant_id`` — operação é cross-tenant
    de sistema. Combinada com:

      * ``REVOKE UPDATE, DELETE FROM PUBLIC`` nas 8 tabelas SCD + log de auditoria
        (migrations 0025 + 0042).
      * ``GRANT INSERT (e SELECT no log) TO tax_table_admin`` (mesmas migrations).

    A sessão tem permissão de INSERT em tabela SCD tributária + INSERT/SELECT
    no audit log. Qualquer outra escrita falha por permissão Postgres — defesa
    em profundidade contra service mal-comportado.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE tax_table_admin"))
        yield session


TaxTableAdminSessionDep = Annotated[
    AsyncSession, Depends(get_tax_table_admin_session)
]
