"""Repositórios — SPED ECD (Sprint 16 PR1).

Lê plano de contas, lançamentos+partidas e saldos mensais para alimentar
o gerador puro (``ecd/gerador.py``). Persiste o ``ArquivoSped`` gerado.

Todas as queries respeitam RLS (sessão tem ``SET LOCAL app.tenant_id``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import (
    ArquivoSped,
    ContaContabil,
    LancamentoContabil,
    PartidaLancamento,
    SaldoContaMes,
)


@dataclass(frozen=True, slots=True)
class LancamentoComPartidas:
    """Lançamento + lista de partidas já carregadas (1 round-trip)."""

    lancamento: LancamentoContabil
    partidas: tuple[tuple[PartidaLancamento, ContaContabil], ...]


@dataclass(frozen=True, slots=True)
class SaldoMensalConta:
    """Linha de saldo_conta_mes enriquecida com o código da conta."""

    conta: ContaContabil
    competencia: date
    saldo_inicial: Decimal
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_final: Decimal


class ContabilParaEcdRepo:
    """Lê o estado contábil de uma empresa para o exercício pedido."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def listar_plano_contas_vigente(
        self, empresa_id: UUID, em: date
    ) -> list[ContaContabil]:
        """Plano de contas vigente em ``em`` (SCD Type 2)."""
        stmt = (
            select(ContaContabil)
            .where(ContaContabil.empresa_id == empresa_id)
            .where(ContaContabil.valid_from <= em)
            .where(
                (ContaContabil.valid_to.is_(None))
                | (ContaContabil.valid_to >= em)
            )
            .order_by(asc(ContaContabil.codigo))
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_lancamentos_do_periodo(
        self,
        empresa_id: UUID,
        periodo_inicio: date,
        periodo_fim: date,
    ) -> list[LancamentoComPartidas]:
        """Lançamentos confirmados/encerrados + partidas + contas (sem N+1).

        Ordem: data_lancamento ASC, depois criado_em ASC — coerente com o
        número sequencial do livro.
        """
        stmt = (
            select(LancamentoContabil)
            .where(LancamentoContabil.empresa_id == empresa_id)
            .where(LancamentoContabil.data_lancamento >= periodo_inicio)
            .where(LancamentoContabil.data_lancamento <= periodo_fim)
            .where(LancamentoContabil.status.in_(("confirmado", "encerrado")))
            .order_by(
                asc(LancamentoContabil.data_lancamento),
                asc(LancamentoContabil.criado_em),
            )
        )
        lancamentos = list((await self._s.execute(stmt)).scalars().all())
        if not lancamentos:
            return []

        lanc_ids = [lanc.id for lanc in lancamentos]
        partida_stmt = (
            select(PartidaLancamento, ContaContabil)
            .join(
                ContaContabil,
                ContaContabil.id == PartidaLancamento.conta_contabil_id,
            )
            .where(PartidaLancamento.lancamento_id.in_(lanc_ids))
            .order_by(
                asc(PartidaLancamento.lancamento_id),
                asc(PartidaLancamento.ordem),
            )
        )
        rows = (await self._s.execute(partida_stmt)).all()

        por_lanc: dict[UUID, list[tuple[PartidaLancamento, ContaContabil]]] = {
            lanc.id: [] for lanc in lancamentos
        }
        for partida, conta in rows:
            por_lanc[partida.lancamento_id].append((partida, conta))

        return [
            LancamentoComPartidas(
                lancamento=lanc, partidas=tuple(por_lanc[lanc.id])
            )
            for lanc in lancamentos
        ]

    async def listar_saldos_mensais(
        self,
        empresa_id: UUID,
        periodo_inicio: date,
        periodo_fim: date,
    ) -> list[SaldoMensalConta]:
        """Saldos mensais materializados (Sprint 9 PR3) no período.

        Ordenado por (competencia, codigo) — garante I150/I155 determinístico.
        """
        stmt = (
            select(SaldoContaMes, ContaContabil)
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia >= periodo_inicio)
            .where(SaldoContaMes.competencia <= periodo_fim)
            .order_by(
                asc(SaldoContaMes.competencia), asc(ContaContabil.codigo)
            )
        )
        rows = (await self._s.execute(stmt)).all()
        return [
            SaldoMensalConta(
                conta=conta,
                competencia=saldo.competencia,
                saldo_inicial=saldo.saldo_inicial,
                total_debitos=saldo.total_debitos,
                total_creditos=saldo.total_creditos,
                saldo_final=saldo.saldo_final,
            )
            for saldo, conta in rows
        ]


class ArquivoSpedRepo:
    """Persistência de ``arquivo_sped`` (RLS pela sessão)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, sped_id: UUID) -> ArquivoSped | None:
        stmt = select(ArquivoSped).where(ArquivoSped.id == sped_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def ativo(
        self,
        empresa_id: UUID,
        tipo: str,
        periodo_inicio: date,
        periodo_fim: date,
    ) -> ArquivoSped | None:
        """Retorna a versão ativa (não-superseded) para a chave de domínio."""
        stmt = select(ArquivoSped).where(
            and_(
                ArquivoSped.empresa_id == empresa_id,
                ArquivoSped.tipo == tipo,
                ArquivoSped.periodo_inicio == periodo_inicio,
                ArquivoSped.periodo_fim == periodo_fim,
                ArquivoSped.superseded_by.is_(None),
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        somente_ativos: bool = True,
        limite: int = 50,
    ) -> list[ArquivoSped]:
        stmt = (
            select(ArquivoSped)
            .where(ArquivoSped.empresa_id == empresa_id)
            .order_by(ArquivoSped.gerado_em.desc())
            .limit(limite)
        )
        if tipo is not None:
            stmt = stmt.where(ArquivoSped.tipo == tipo)
        if somente_ativos:
            stmt = stmt.where(ArquivoSped.superseded_by.is_(None))
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, arquivo: ArquivoSped) -> ArquivoSped:
        self._s.add(arquivo)
        await self._s.flush()
        return arquivo

    async def marcar_superseded(
        self, anterior: ArquivoSped, novo_id: UUID
    ) -> None:
        anterior.superseded_by = novo_id
        await self._s.flush()
