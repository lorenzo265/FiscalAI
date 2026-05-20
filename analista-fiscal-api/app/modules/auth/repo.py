from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import Tenant, Usuario


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
