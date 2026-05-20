"""Repositórios do módulo ICMS (Sprint 11 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import AliquotaIcmsUf, ApuracaoFiscal


class AliquotaIcmsRepo:
    """Leitura SCD (§8.3) das alíquotas internas por UF."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def vigente_para_uf(
        self, uf: str, em: date
    ) -> tuple[Decimal, Decimal] | None:
        """Retorna (alíquota_interna, FECP) vigentes, ou None se não houver."""
        stmt = (
            select(AliquotaIcmsUf.aliquota_interna, AliquotaIcmsUf.aliquota_fecp)
            .where(AliquotaIcmsUf.uf == uf)
            .where(AliquotaIcmsUf.valid_from <= em)
            .where(
                (AliquotaIcmsUf.valid_to == None)  # noqa: E711
                | (AliquotaIcmsUf.valid_to >= em)
            )
            .order_by(AliquotaIcmsUf.valid_from.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1]


class ApuracaoIcmsRepo:
    """Persiste no ``apuracao_fiscal`` (tabela central da Sprint 2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar(
        self, empresa_id: UUID, competencia: date
    ) -> ApuracaoFiscal | None:
        stmt = select(ApuracaoFiscal).where(
            ApuracaoFiscal.empresa_id == empresa_id,
            ApuracaoFiscal.competencia == competencia,
            ApuracaoFiscal.tipo == "icms",
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self, empresa_id: UUID, *, limite: int = 24
    ) -> list[ApuracaoFiscal]:
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.tipo == "icms")
            .order_by(ApuracaoFiscal.competencia.desc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, apuracao: ApuracaoFiscal) -> ApuracaoFiscal:
        self._s.add(apuracao)
        await self._s.flush()
        await self._s.refresh(apuracao)
        return apuracao
