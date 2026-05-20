"""Service de relatórios contábeis — balancete, diário, razão (Sprint 9 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import and_, asc, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.relatorios import (
    LancamentoRazaoView,
    LinhaBalancete,
    LinhaRazao,
    MovimentacaoConta,
    consolidar_balancete,
    consolidar_razao,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import (
    ContaContabil,
    LancamentoContabil,
    PartidaLancamento,
    SaldoContaMes,
)
from app.shared.exceptions import (
    ContaContabilNaoEncontrada,
    EmpresaNaoEncontrada,
)

log = structlog.get_logger(__name__)


class RelatoriosService:
    """Queries de balancete, diário e razão. Sem mutação."""

    # ── Balancete ────────────────────────────────────────────────────────────

    async def balancete(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        competencia: date,
    ) -> list[LinhaBalancete]:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        proximo_mes = _proximo_mes(comp_mes1)

        # Subquery agregada por conta dentro do mês.
        soma_d = func.coalesce(
            func.sum(
                case((PartidaLancamento.tipo == "D", PartidaLancamento.valor), else_=0)
            ),
            0,
        )
        soma_c = func.coalesce(
            func.sum(
                case((PartidaLancamento.tipo == "C", PartidaLancamento.valor), else_=0)
            ),
            0,
        )

        stmt = (
            select(
                ContaContabil.id,
                ContaContabil.codigo,
                ContaContabil.descricao,
                ContaContabil.natureza,
                ContaContabil.tipo,
                ContaContabil.nivel,
                soma_d.label("d"),
                soma_c.label("c"),
            )
            .select_from(ContaContabil)
            .outerjoin(
                PartidaLancamento,
                PartidaLancamento.conta_contabil_id == ContaContabil.id,
            )
            .outerjoin(
                LancamentoContabil,
                and_(
                    LancamentoContabil.id == PartidaLancamento.lancamento_id,
                    LancamentoContabil.competencia >= comp_mes1,
                    LancamentoContabil.competencia < proximo_mes,
                    LancamentoContabil.status.in_(["confirmado", "encerrado"]),
                ),
            )
            .where(ContaContabil.empresa_id == empresa_id)
            .where(ContaContabil.aceita_lancamento.is_(True))
            .where(
                or_(
                    ContaContabil.valid_to.is_(None),
                    ContaContabil.valid_to >= comp_mes1,
                )
            )
            .where(ContaContabil.valid_from <= comp_mes1)
            .group_by(
                ContaContabil.id,
                ContaContabil.codigo,
                ContaContabil.descricao,
                ContaContabil.natureza,
                ContaContabil.tipo,
                ContaContabil.nivel,
            )
        )
        rows = (await session.execute(stmt)).all()

        # Saldo inicial = saldo final do mês anterior em saldo_conta_mes.
        # No MVP, se não houver saldo anterior, assume 0.
        saldos_iniciais = await self._saldos_finais_anteriores(
            session, empresa_id, comp_mes1
        )

        movimentacoes = [
            MovimentacaoConta(
                conta_id=r.id,
                codigo=r.codigo,
                descricao=r.descricao,
                natureza=r.natureza,
                tipo=r.tipo,
                nivel=r.nivel,
                saldo_inicial=saldos_iniciais.get(r.id, Decimal("0")),
                total_debitos=Decimal(str(r.d or "0")),
                total_creditos=Decimal(str(r.c or "0")),
            )
            for r in rows
        ]
        return consolidar_balancete(movimentacoes)

    async def _saldos_finais_anteriores(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        competencia: date,
    ) -> dict[UUID, Decimal]:
        """Última snapshot ``saldo_conta_mes`` antes da competência."""
        mes_anterior = _mes_anterior(competencia)
        stmt = select(
            SaldoContaMes.conta_contabil_id, SaldoContaMes.saldo_final
        ).where(
            SaldoContaMes.empresa_id == empresa_id,
            SaldoContaMes.competencia == mes_anterior,
        )
        rows = (await session.execute(stmt)).all()
        return {r.conta_contabil_id: Decimal(str(r.saldo_final)) for r in rows}

    # ── Diário ──────────────────────────────────────────────────────────────

    async def diario(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        *,
        desde: date | None,
        ate: date | None,
    ) -> list[LancamentoContabil]:
        await self._garantir_empresa(session, empresa_id)
        stmt = (
            select(LancamentoContabil)
            .where(LancamentoContabil.empresa_id == empresa_id)
            .where(
                LancamentoContabil.status.in_(["confirmado", "encerrado"])
            )
        )
        if desde is not None:
            stmt = stmt.where(LancamentoContabil.data_lancamento >= desde)
        if ate is not None:
            stmt = stmt.where(LancamentoContabil.data_lancamento <= ate)
        stmt = stmt.order_by(
            asc(LancamentoContabil.data_lancamento),
            asc(LancamentoContabil.criado_em),
        )
        return list((await session.execute(stmt)).scalars().all())

    # ── Razão ───────────────────────────────────────────────────────────────

    async def razao(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        conta_id: UUID,
        competencia: date,
    ) -> tuple[ContaContabil, Decimal, list[LinhaRazao]]:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        proximo_mes = _proximo_mes(comp_mes1)

        # Conta
        conta = (
            await session.execute(
                select(ContaContabil).where(
                    ContaContabil.id == conta_id,
                    ContaContabil.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if conta is None:
            raise ContaContabilNaoEncontrada(
                f"Conta {conta_id} não encontrada nesta empresa"
            )

        # Saldo inicial: snapshot do mês anterior, ou 0.
        anteriores = await self._saldos_finais_anteriores(
            session, empresa_id, comp_mes1
        )
        saldo_inicial = anteriores.get(conta_id, Decimal("0"))

        # Lançamentos dentro do mês para esta conta.
        stmt = (
            select(
                LancamentoContabil.id,
                LancamentoContabil.data_lancamento,
                LancamentoContabil.historico,
                PartidaLancamento.tipo,
                PartidaLancamento.valor,
                LancamentoContabil.criado_em,
            )
            .join(
                PartidaLancamento,
                PartidaLancamento.lancamento_id == LancamentoContabil.id,
            )
            .where(LancamentoContabil.empresa_id == empresa_id)
            .where(PartidaLancamento.conta_contabil_id == conta_id)
            .where(
                LancamentoContabil.competencia >= comp_mes1,
                LancamentoContabil.competencia < proximo_mes,
            )
            .where(
                LancamentoContabil.status.in_(["confirmado", "encerrado"])
            )
            .order_by(
                asc(LancamentoContabil.data_lancamento),
                asc(LancamentoContabil.criado_em),
            )
        )
        rows = (await session.execute(stmt)).all()
        views = [
            LancamentoRazaoView(
                lancamento_id=r.id,
                data_lancamento=r.data_lancamento,
                historico=r.historico,
                tipo=r.tipo,
                valor=Decimal(str(r.valor)),
            )
            for r in rows
        ]
        linhas = consolidar_razao(conta.natureza, saldo_inicial, views)
        return conta, saldo_inicial, linhas

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _garantir_empresa(
        self, session: AsyncSession, empresa_id: UUID
    ) -> None:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")


def _proximo_mes(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _mes_anterior(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)
