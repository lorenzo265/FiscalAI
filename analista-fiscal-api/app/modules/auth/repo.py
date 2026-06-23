from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import RefreshToken, Tenant, Usuario


class TenantRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug, Tenant.ativo.is_(True))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def slug_existe(self, slug: str) -> bool:
        stmt = select(Tenant.id).where(Tenant.slug == slug)
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def criar(self, nome: str, slug: str) -> Tenant:
        tenant = Tenant(nome=nome, slug=slug)
        self._s.add(tenant)
        await self._s.flush()
        return tenant


class UsuarioRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_email(self, tenant_id: UUID, email: str) -> Usuario | None:
        stmt = select(Usuario).where(
            Usuario.tenant_id == tenant_id,
            Usuario.email == email,
            Usuario.ativo.is_(True),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def email_existe(self, tenant_id: UUID, email: str) -> bool:
        stmt = select(Usuario.id).where(Usuario.tenant_id == tenant_id, Usuario.email == email)
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def criar(
        self,
        tenant_id: UUID,
        nome: str,
        email: str,
        senha_hash: str,
    ) -> Usuario:
        usuario = Usuario(
            tenant_id=tenant_id,
            nome=nome,
            email=email,
            senha_hash=senha_hash,
        )
        self._s.add(usuario)
        await self._s.flush()
        return usuario


class RefreshTokenRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar(
        self,
        *,
        tenant_id: UUID,
        usuario_id: UUID,
        family_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._s.add(token)
        await self._s.flush()
        return token

    async def por_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def revogar_familia(self, family_id: UUID, *, momento: datetime) -> None:
        """Revoga toda a linhagem (deteccao de reuso)."""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=momento)
        )
        await self._s.execute(stmt)

    async def revogar_do_tenant(self, tenant_id: UUID, *, momento: datetime) -> int:
        """Revoga todos os refresh tokens vivos do tenant (ex.: exclusao LGPD).

        Retorna quantos foram revogados.
        """
        sel = select(RefreshToken.id).where(
            RefreshToken.tenant_id == tenant_id,
            RefreshToken.revoked_at.is_(None),
        )
        ids = (await self._s.execute(sel)).scalars().all()
        if ids:
            await self._s.execute(
                update(RefreshToken)
                .where(RefreshToken.id.in_(ids))
                .values(revoked_at=momento)
            )
        return len(ids)
