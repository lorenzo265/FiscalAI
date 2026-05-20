"""Repositórios — bem, depreciação, tabela RFB (Sprint 8 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import (
    BemImobilizado,
    DepreciacaoMensal,
    TabelaDepreciacaoRfb,
)


class TabelaDepreciacaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def taxa_vigente(
        self, categoria: str, em: date
    ) -> TabelaDepreciacaoRfb | None:
        """Retorna a linha vigente em ``em`` para a categoria."""
        stmt = (
            select(TabelaDepreciacaoRfb)
            .where(
                TabelaDepreciacaoRfb.categoria == categoria,
                TabelaDepreciacaoRfb.valid_from <= em,
            )
            .where(
                (TabelaDepreciacaoRfb.valid_to.is_(None))
                | (TabelaDepreciacaoRfb.valid_to >= em)
            )
            .order_by(desc(TabelaDepreciacaoRfb.valid_from))
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


class BemImobilizadoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        descricao: str,
        categoria: str,
        data_aquisicao: date,
        valor_aquisicao: Decimal,
        taxa_depreciacao_anual: Decimal,
        vida_util_meses: int,
        valor_residual: Decimal,
        metodo_depreciacao: str,
        documento_fiscal_id: UUID | None,
        conta_contabil_id: UUID | None,
    ) -> BemImobilizado:
        bem = BemImobilizado(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            descricao=descricao,
            categoria=categoria,
            data_aquisicao=data_aquisicao,
            valor_aquisicao=valor_aquisicao,
            taxa_depreciacao_anual=taxa_depreciacao_anual,
            vida_util_meses=vida_util_meses,
            valor_residual=valor_residual,
            metodo_depreciacao=metodo_depreciacao,
            documento_fiscal_id=documento_fiscal_id,
            conta_contabil_id=conta_contabil_id,
        )
        self._s.add(bem)
        await self._s.flush()
        return bem

    async def por_id(self, bem_id: UUID) -> BemImobilizado | None:
        stmt = select(BemImobilizado).where(BemImobilizado.id == bem_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(self, empresa_id: UUID) -> list[BemImobilizado]:
        stmt = (
            select(BemImobilizado)
            .where(BemImobilizado.empresa_id == empresa_id)
            .order_by(asc(BemImobilizado.data_aquisicao))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_ativos_depreciaveis(
        self, empresa_id: UUID
    ) -> list[BemImobilizado]:
        """Bens ativos sem data_baixa — candidatos a entrar no lote mensal."""
        stmt = (
            select(BemImobilizado)
            .where(
                BemImobilizado.empresa_id == empresa_id,
                BemImobilizado.ativo.is_(True),
                BemImobilizado.data_baixa.is_(None),
            )
            .order_by(asc(BemImobilizado.data_aquisicao))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def baixar(
        self, bem: BemImobilizado, *, data_baixa: date, motivo: str
    ) -> None:
        bem.data_baixa = data_baixa
        bem.motivo_baixa = motivo
        bem.ativo = False
        await self._s.flush()


class DepreciacaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar_acumulado_ate(
        self, bem_id: UUID, *, exclusive_competencia: date
    ) -> Decimal:
        """Soma de ``valor_depreciado`` até (mas excluindo) a competência informada."""
        stmt = select(func.coalesce(func.sum(DepreciacaoMensal.valor_depreciado), 0)).where(
            DepreciacaoMensal.bem_id == bem_id,
            DepreciacaoMensal.competencia < exclusive_competencia,
        )
        valor = (await self._s.execute(stmt)).scalar_one()
        return Decimal(str(valor or "0"))

    async def existe(self, bem_id: UUID, competencia: date) -> bool:
        stmt = select(DepreciacaoMensal.id).where(
            DepreciacaoMensal.bem_id == bem_id,
            DepreciacaoMensal.competencia == competencia,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def criar(
        self,
        *,
        tenant_id: UUID,
        bem_id: UUID,
        competencia: date,
        valor_depreciado: Decimal,
        valor_acumulado: Decimal,
        saldo_contabil: Decimal,
    ) -> DepreciacaoMensal:
        registro = DepreciacaoMensal(
            tenant_id=tenant_id,
            bem_id=bem_id,
            competencia=competencia,
            valor_depreciado=valor_depreciado,
            valor_acumulado=valor_acumulado,
            saldo_contabil=saldo_contabil,
        )
        self._s.add(registro)
        await self._s.flush()
        return registro

    async def listar_por_bem(self, bem_id: UUID) -> list[DepreciacaoMensal]:
        stmt = (
            select(DepreciacaoMensal)
            .where(DepreciacaoMensal.bem_id == bem_id)
            .order_by(asc(DepreciacaoMensal.competencia))
        )
        return list((await self._s.execute(stmt)).scalars().all())
