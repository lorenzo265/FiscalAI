"""Repositórios — marketplace (Sprint 13 PR1/PR2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ConsultaMarketplace, ContadorParceiro


class ContadorParceiroRepo:
    """CRUD básico do pool global de parceiros.

    ``ContadorParceiro`` não tem ``tenant_id`` — sessão usada por esse repo
    geralmente é a anônima (sem RLS) ou a do parceiro autenticado (PR3).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, parceiro_id: UUID) -> ContadorParceiro | None:
        stmt = select(ContadorParceiro).where(ContadorParceiro.id == parceiro_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_email(self, email: str) -> ContadorParceiro | None:
        stmt = select(ContadorParceiro).where(ContadorParceiro.email == email)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_crc(self, crc_numero: str, crc_uf: str) -> ContadorParceiro | None:
        stmt = select(ContadorParceiro).where(
            ContadorParceiro.crc_numero == crc_numero,
            ContadorParceiro.crc_uf == crc_uf,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(self, parceiro: ContadorParceiro) -> ContadorParceiro:
        self._s.add(parceiro)
        await self._s.flush()
        await self._s.refresh(parceiro)
        return parceiro

    async def listar(
        self,
        *,
        somente_ativos: bool = False,
        limite: int = 100,
    ) -> list[ContadorParceiro]:
        stmt = (
            select(ContadorParceiro)
            .order_by(ContadorParceiro.created_at.desc())
            .limit(limite)
        )
        if somente_ativos:
            stmt = stmt.where(
                ContadorParceiro.ativo.is_(True),
                ContadorParceiro.crc_status == "ativo",
            )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_ativos(self, limite: int = 500) -> list[ContadorParceiro]:
        """Lista TODOS os parceiros ativos+CRC ativo — para o matching em memória.

        Volume baixo no MVP (dezenas → algumas centenas). Quando crescer,
        promover filtro de especialidade/UF para query SQL.
        """
        stmt = (
            select(ContadorParceiro)
            .where(
                ContadorParceiro.ativo.is_(True),
                ContadorParceiro.crc_status == "ativo",
            )
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())


class ConsultaRepo:
    """CRUD da ``consulta_marketplace`` — RLS dual aplicada na sessão."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, consulta_id: UUID) -> ConsultaMarketplace | None:
        stmt = select(ConsultaMarketplace).where(
            ConsultaMarketplace.id == consulta_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_idempotency_key(
        self, idempotency_key: UUID
    ) -> ConsultaMarketplace | None:
        stmt = select(ConsultaMarketplace).where(
            ConsultaMarketplace.idempotency_key == idempotency_key
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_por_empresa(
        self,
        empresa_id: UUID,
        *,
        status: str | None = None,
        limite: int = 50,
    ) -> list[ConsultaMarketplace]:
        stmt = (
            select(ConsultaMarketplace)
            .where(ConsultaMarketplace.empresa_id == empresa_id)
            .order_by(desc(ConsultaMarketplace.aberta_em))
            .limit(limite)
        )
        if status:
            stmt = stmt.where(ConsultaMarketplace.status == status)
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_por_contador(
        self,
        contador_id: UUID,
        *,
        status: str | None = None,
        limite: int = 50,
    ) -> list[ConsultaMarketplace]:
        stmt = (
            select(ConsultaMarketplace)
            .where(ConsultaMarketplace.contador_id == contador_id)
            .order_by(desc(ConsultaMarketplace.aberta_em))
            .limit(limite)
        )
        if status:
            stmt = stmt.where(ConsultaMarketplace.status == status)
        return list((await self._s.execute(stmt)).scalars().all())

    async def avaliacoes_recentes(
        self, contador_id: UUID, limite: int = 10
    ) -> list[int]:
        """Devolve os últimos ``limite`` ratings_cliente não-NULL, mais recente primeiro."""
        stmt = (
            select(ConsultaMarketplace.rating_cliente)
            .where(
                ConsultaMarketplace.contador_id == contador_id,
                ConsultaMarketplace.rating_cliente.is_not(None),
            )
            .order_by(desc(ConsultaMarketplace.respondida_em))
            .limit(limite)
        )
        return [
            r for r in (await self._s.execute(stmt)).scalars().all() if r is not None
        ]

    async def inserir_idempotente(
        self,
        values: dict[str, Any],
    ) -> ConsultaMarketplace:
        """INSERT atômico com ``ON CONFLICT DO NOTHING`` em ``idempotency_key``.

        Se a consulta já existe (mesma idempotency_key), devolve a linha
        existente. Caller é responsável por garantir que ``values`` contenha
        ``idempotency_key``.
        """
        key: UUID = values["idempotency_key"]
        stmt = (
            pg_insert(ConsultaMarketplace)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        await self._s.execute(stmt)
        # Sempre re-busca: cobre tanto o caso "INSERT inseriu" quanto
        # "ON CONFLICT virou no-op" sem depender de rowcount + RETURNING
        # (que não funciona com DO NOTHING em todas as versões do dialect).
        existing = await self.por_idempotency_key(key)
        if existing is None:
            # Insertion succeeded but row not visible — defesa em profundidade.
            raise RuntimeError(
                f"Falha inesperada inserindo consulta com key={key}"
            )
        return existing
