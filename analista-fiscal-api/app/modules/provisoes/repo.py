"""Repositório de provisões trabalhistas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ProvisaoMensal


class ProvisoesRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert_agregada(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
        tipo: str,
        base_calculo: Decimal,
        aliquota: Decimal,
        valor_provisao: Decimal,
        algoritmo_versao: str,
    ) -> bool:
        """Insere provisão agregada (funcionario_id NULL).

        Retorna True se inseriu (False se já existia — UNIQUE parcial pegou).
        Idempotência §8.9 via ON CONFLICT DO NOTHING no índice
        ``uq_provisao_agregada``.
        """
        stmt = (
            pg_insert(ProvisaoMensal)
            .values(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                funcionario_id=None,
                competencia=competencia,
                tipo=tipo,
                base_calculo=base_calculo,
                aliquota=aliquota,
                valor_provisao=valor_provisao,
                algoritmo_versao=algoritmo_versao,
            )
            .on_conflict_do_nothing(index_elements=["empresa_id", "competencia", "tipo"])
            .returning(ProvisaoMensal.id)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def listar(
        self,
        empresa_id: UUID,
        *,
        competencia: date | None = None,
        tipo: str | None = None,
    ) -> list[ProvisaoMensal]:
        stmt = select(ProvisaoMensal).where(ProvisaoMensal.empresa_id == empresa_id)
        if competencia is not None:
            stmt = stmt.where(ProvisaoMensal.competencia == competencia)
        if tipo is not None:
            stmt = stmt.where(ProvisaoMensal.tipo == tipo)
        stmt = stmt.order_by(
            desc(ProvisaoMensal.competencia), ProvisaoMensal.tipo
        )
        return list((await self._s.execute(stmt)).scalars().all())
