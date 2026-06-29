from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.auth.repo import RefreshTokenRepo, TenantRepo, UsuarioRepo
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.shared.auth.jwt import TenantContext, criar_token
from app.shared.auth.password import hash_senha, verificar_senha
from app.shared.auth.refresh_token import gerar_refresh_token, hash_refresh_token
from app.shared.db.models import Tenant, Usuario
from app.shared.db.rls import set_tenant_id
from app.shared.exceptions import (
    CredenciaisInvalidas,
    EmailJaCadastrado,
    SlugJaCadastrado,
    TenantNaoEncontrado,
    TokenInvalido,
)
from app.shared.integrations.email.templates import renderizar_onboarding
from app.workers.tasks.email_enviar import enfileirar_email

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class AuthService:
    async def _emitir_refresh(
        self, session: AsyncSession, *, tenant_id: UUID, usuario_id: UUID
    ) -> str:
        """Cria um refresh token (nova família) e devolve o valor CRU (uma vez)."""
        raw = gerar_refresh_token()
        expires_at = datetime.now(tz=_TZ_BR) + timedelta(
            days=get_settings().JWT_REFRESH_EXPIRE_DAYS
        )
        await RefreshTokenRepo(session).criar(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            family_id=uuid4(),
            token_hash=hash_refresh_token(raw),
            expires_at=expires_at,
        )
        return raw

    async def registrar(
        self,
        session: AsyncSession,
        payload: RegisterIn,
    ) -> tuple[Tenant, Usuario, str, int, str]:
        """Cria tenant + usuário admin em uma transação.

        Retorna (tenant, usuario, access_token, expires_in, refresh_token).
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

        raw_refresh = await self._emitir_refresh(
            session, tenant_id=tenant.id, usuario_id=usuario.id
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

        # E-mail de boas-vindas (fail-soft — NUNCA pode quebrar o cadastro).
        # Despacho assíncrono via Celery; no-op sem broker, fake sem EMAIL_API_KEY.
        try:
            msg = renderizar_onboarding(
                nome=usuario.nome,
                link_painel=get_settings().APP_BASE_URL,
            )
            enfileirar_email(msg, to=usuario.email, tags=["onboarding"])
        except Exception:  # notificação nunca bloqueia o cadastro
            log.warning("auth.onboarding_email_falhou", tenant_id=str(tenant.id))

        return tenant, usuario, token, expires_in, raw_refresh

    async def login(
        self,
        session: AsyncSession,
        payload: LoginIn,
    ) -> tuple[str, int, str]:
        """Autentica usuário por tenant_slug + email + senha.

        Retorna (access_token, expires_in, refresh_token).
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
        raw_refresh = await self._emitir_refresh(
            session, tenant_id=tenant.id, usuario_id=usuario.id
        )
        await session.commit()

        log.info(
            "auth.login",
            tenant_id=str(tenant.id),
            usuario_id=str(usuario.id),
        )
        return token, expires_in, raw_refresh

    async def renovar(
        self, session: AsyncSession, *, raw_token: str
    ) -> tuple[str, int, str]:
        """Rotaciona o refresh token e emite um novo access token.

        Sessão de SISTEMA (superuser, bypassa RLS): a busca é por hash global,
        pré-autenticação. Detecção de reuso: um token já revogado apresentado de
        novo significa roubo -> a família inteira é revogada.

        Retorna (access_token, expires_in, novo_refresh_token).
        """
        repo = RefreshTokenRepo(session)
        registro = await repo.por_hash(hash_refresh_token(raw_token))
        agora = datetime.now(tz=_TZ_BR)

        if registro is None:
            raise TokenInvalido("Refresh token inválido")
        if registro.revoked_at is not None:
            await repo.revogar_familia(registro.family_id, momento=agora)
            await session.commit()
            log.warning(
                "auth.refresh.reuso_detectado",
                family_id=str(registro.family_id),
                tenant_id=str(registro.tenant_id),
            )
            raise TokenInvalido("Refresh token já utilizado — família revogada")
        if registro.expires_at <= agora:
            raise TokenInvalido("Refresh token expirado")

        # Rotaciona: revoga o atual e emite um novo na MESMA família.
        registro.revoked_at = agora
        raw_novo = gerar_refresh_token()
        expires_at = agora + timedelta(days=get_settings().JWT_REFRESH_EXPIRE_DAYS)
        await repo.criar(
            tenant_id=registro.tenant_id,
            usuario_id=registro.usuario_id,
            family_id=registro.family_id,
            token_hash=hash_refresh_token(raw_novo),
            expires_at=expires_at,
        )
        token, expires_in = criar_token(
            TenantContext(
                tenant_id=registro.tenant_id, usuario_id=registro.usuario_id
            )
        )
        await session.commit()
        log.info(
            "auth.refresh.rotacionado",
            tenant_id=str(registro.tenant_id),
            usuario_id=str(registro.usuario_id),
        )
        return token, expires_in, raw_novo
