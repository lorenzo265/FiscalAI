"""Repositórios — plano de contas, lançamentos, partidas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import (
    ContaContabil,
    LancamentoContabil,
    PartidaLancamento,
    SaldoContaMes,
)


class ContaContabilRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, conta_id: UUID) -> ContaContabil | None:
        stmt = select(ContaContabil).where(ContaContabil.id == conta_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_codigo(
        self, empresa_id: UUID, codigo: str, *, em: date | None = None
    ) -> ContaContabil | None:
        """Retorna a conta vigente em ``em`` para o código informado."""
        stmt = select(ContaContabil).where(
            ContaContabil.empresa_id == empresa_id,
            ContaContabil.codigo == codigo,
        )
        if em is not None:
            stmt = stmt.where(ContaContabil.valid_from <= em).where(
                (ContaContabil.valid_to.is_(None)) | (ContaContabil.valid_to >= em)
            )
        stmt = stmt.order_by(desc(ContaContabil.valid_from)).limit(1)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(self, empresa_id: UUID) -> list[ContaContabil]:
        stmt = (
            select(ContaContabil)
            .where(
                ContaContabil.empresa_id == empresa_id,
                ContaContabil.valid_to.is_(None),
            )
            .order_by(asc(ContaContabil.codigo))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def carregar_para_validacao(
        self, conta_ids: list[UUID]
    ) -> dict[UUID, ContaContabil]:
        if not conta_ids:
            return {}
        stmt = select(ContaContabil).where(ContaContabil.id.in_(conta_ids))
        rows = (await self._s.execute(stmt)).scalars().all()
        return {c.id: c for c in rows}

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        codigo: str,
        descricao: str,
        parent_id: UUID | None,
        natureza: str,
        tipo: str,
        nivel: int,
        aceita_lancamento: bool,
        codigo_ecd_referencial: str | None,
        valid_from: date,
    ) -> ContaContabil:
        conta = ContaContabil(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            codigo=codigo,
            descricao=descricao,
            parent_id=parent_id,
            natureza=natureza,
            tipo=tipo,
            nivel=nivel,
            aceita_lancamento=aceita_lancamento,
            codigo_ecd_referencial=codigo_ecd_referencial,
            valid_from=valid_from,
        )
        self._s.add(conta)
        await self._s.flush()
        return conta


class LancamentoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, lancamento_id: UUID) -> LancamentoContabil | None:
        stmt = select(LancamentoContabil).where(LancamentoContabil.id == lancamento_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_origem(
        self, origem_tipo: str, origem_id: UUID
    ) -> LancamentoContabil | None:
        stmt = select(LancamentoContabil).where(
            LancamentoContabil.origem_tipo == origem_tipo,
            LancamentoContabil.origem_id == origem_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        data_lancamento: date,
        competencia: date,
        historico: str,
        origem_tipo: str,
        origem_id: UUID | None,
        total_debito: Decimal,
        total_credito: Decimal,
        status: str = "rascunho",
    ) -> LancamentoContabil:
        lanc = LancamentoContabil(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            data_lancamento=data_lancamento,
            competencia=competencia,
            historico=historico,
            origem_tipo=origem_tipo,
            origem_id=origem_id,
            total_debito=total_debito,
            total_credito=total_credito,
            status=status,
        )
        self._s.add(lanc)
        await self._s.flush()
        return lanc

    async def confirmar(self, lancamento: LancamentoContabil) -> None:
        lancamento.status = "confirmado"
        await self._s.flush()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        competencia: date | None = None,
        status: str | None = None,
    ) -> list[LancamentoContabil]:
        stmt = select(LancamentoContabil).where(
            LancamentoContabil.empresa_id == empresa_id
        )
        if competencia is not None:
            stmt = stmt.where(LancamentoContabil.competencia == competencia)
        if status is not None:
            stmt = stmt.where(LancamentoContabil.status == status)
        stmt = stmt.order_by(
            desc(LancamentoContabil.data_lancamento),
            desc(LancamentoContabil.criado_em),
        )
        return list((await self._s.execute(stmt)).scalars().all())


class PartidaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def criar_lote(
        self,
        *,
        tenant_id: UUID,
        lancamento_id: UUID,
        partidas: list[tuple[UUID, str, Decimal]],
    ) -> list[PartidaLancamento]:
        """``partidas``: lista de tuplas (conta_id, tipo D/C, valor)."""
        criadas: list[PartidaLancamento] = []
        for ordem, (conta_id, tipo, valor) in enumerate(partidas, start=1):
            partida = PartidaLancamento(
                tenant_id=tenant_id,
                lancamento_id=lancamento_id,
                conta_contabil_id=conta_id,
                tipo=tipo,
                valor=valor,
                ordem=ordem,
            )
            self._s.add(partida)
            criadas.append(partida)
        await self._s.flush()
        return criadas

    async def por_lancamento(self, lancamento_id: UUID) -> list[PartidaLancamento]:
        stmt = (
            select(PartidaLancamento)
            .where(PartidaLancamento.lancamento_id == lancamento_id)
            .order_by(asc(PartidaLancamento.ordem))
        )
        return list((await self._s.execute(stmt)).scalars().all())


class SaldoContaMesRepo:
    """Acessor de ``saldo_conta_mes`` — materialização do balancete mensal."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def competencia_encerrada(
        self, empresa_id: UUID, competencia: date
    ) -> bool:
        """True se houver pelo menos uma linha ``status='fechado'`` na competência.

        Usado como guarda em ``criar_lancamento_manual`` — defesa em
        profundidade além do CHECK de ``status`` em ``lancamento_contabil``.
        """
        stmt = (
            select(SaldoContaMes.id)
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia == competencia)
            .where(SaldoContaMes.status == "fechado")
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None
