from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.repo import TenantRepo, UsuarioRepo
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.shared.auth.jwt import TenantContext, criar_token
from app.shared.auth.password import hash_senha, verificar_senha
from app.shared.db.models import Tenant, Usuario
from app.shared.db.rls import set_tenant_id
from app.shared.exceptions import (
    CredenciaisInvalidas,
    EmailJaCadastrado,
    SlugJaCadastrado,
    TenantNaoEncontrado,
)

log = structlog.get_logger(__name__)


class AuthService:
    async def registrar(
        self,
        session: AsyncSession,
        payload: RegisterIn,
    ) -> tuple[Tenant, Usuario, str, int]:
        """Cria tenant + usuário admin em uma transação.

        Retorna (tenant, usuario, access_token, expires_in).
        """
        tenant_repo = TenantRepo(session)
        usuario_repo = UsuarioRepo(session)

        if await tenant_repo.slug_existe(payload.tenant_slug):
            raise SlugJaCadastrado(f"Slug '{payload.tenant_slug}' já está em uso")

        tenant = await tenant_repo.criar(payload.tenant_nome, payload.tenant_slug)

        # Ativa RLS para o novo tenant antes de inserir usuário
        await set_tenant_id(session, tenant.id)

        if await usuario_repo.email_existe(tenant.id, payload.usuario_email):
            raise EmailJaCadastrado(f"E-mail '{payload.usuario_email}' já cadastrado")

        usuario = await usuario_repo.criar(
            tenant_id=tenant.id,
            nome=payload.usuario_nome,
            email=payload.usuario_email,
            senha_hash=hash_senha(payload.usuario_senha),
        )

        await session.commit()

        ctx = TenantContext(tenant_id=tenant.id, usuario_id=usuario.id)
        token, expires_in = criar_token(ctx)

        log.info(
            "auth.registrou",
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            usuario_id=str(usuario.id),
        )
        return tenant, usuario, token, expires_in

    async def login(
        self,
        session: AsyncSession,
        payload: LoginIn,
    ) -> tuple[str, int]:
        """Autentica usuário por tenant_slug + email + senha.

        Retorna (access_token, expires_in).
        """
        tenant_repo = TenantRepo(session)
        usuario_repo = UsuarioRepo(session)

        tenant = await tenant_repo.por_slug(payload.tenant_slug)
        if tenant is None:
            raise TenantNaoEncontrado(f"Tenant '{payload.tenant_slug}' não encontrado")

        # Ativa RLS para o tenant antes de consultar usuários
        await set_tenant_id(session, tenant.id)

        usuario = await usuario_repo.por_email(tenant.id, payload.email)
        if usuario is None or not verificar_senha(payload.senha, usuario.senha_hash):
            raise CredenciaisInvalidas("E-mail ou senha incorretos")

        ctx = TenantContext(tenant_id=tenant.id, usuario_id=usuario.id)
        token, expires_in = criar_token(ctx)

        log.info(
            "auth.login",
            tenant_id=str(tenant.id),
            usuario_id=str(usuario.id),
        )
        return token, expires_in
