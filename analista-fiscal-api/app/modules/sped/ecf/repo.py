"""Repositórios — SPED ECF (Sprint 16 PR2).

Lê apurações IRPJ/CSLL trimestrais persistidas (Sprint 11 PR1), plano de
contas vigente em 31/12, saldos contábeis ao fim de cada trimestre e
ECD vinculada do mesmo ano (se existir — populada na PR1 desta sprint).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fiscal.snapshots import (
    CsllLpSnapshot,
    IrpjLpSnapshot,
    parse_apuracao_output,
)
from app.shared.db.models import (
    ApuracaoFiscal,
    ArquivoSped,
    ContaContabil,
    SaldoContaMes,
)


@dataclass(frozen=True, slots=True)
class ApuracaoTrimestreLp:
    """Par IRPJ + CSLL apurados num mesmo trimestre.

    ``numero`` ∈ 1..4. Datas computadas pelo service a partir do ano.
    """

    numero: int
    irpj: IrpjLpSnapshot
    csll: CsllLpSnapshot
    competencia: date  # 1º dia do trimestre (chave canônica usada no DB)


@dataclass(frozen=True, slots=True)
class SaldoTrimestreConta:
    """Saldo final de uma conta no fim do trimestre — input do K155."""

    conta: ContaContabil
    debitos_acumulados: Decimal
    creditos_acumulados: Decimal
    saldo_inicial: Decimal
    saldo_final: Decimal


class ApuracoesLpParaEcfRepo:
    """Carrega as 4 apurações IRPJ + 4 CSLL do exercício LP."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def listar_trimestres_do_ano(
        self, empresa_id: UUID, ano: int
    ) -> list[ApuracaoTrimestreLp]:
        """Junta IRPJ e CSLL por trimestre. Retorna ordenado por numero.

        Trimestre é identificado pela competência do registro em
        ``apuracao_fiscal`` (sempre o 1º dia do trimestre — convenção do
        service da Sprint 11 PR1: 01-jan, 01-abr, 01-jul, 01-out).
        """
        ini = date(ano, 1, 1)
        fim = date(ano, 12, 31)
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia >= ini)
            .where(ApuracaoFiscal.competencia <= fim)
            .where(ApuracaoFiscal.tipo.in_(("irpj", "csll")))
            .order_by(asc(ApuracaoFiscal.competencia), asc(ApuracaoFiscal.tipo))
        )
        rows = list((await self._s.execute(stmt)).scalars().all())

        por_competencia: dict[date, dict[str, ApuracaoFiscal]] = defaultdict(dict)
        for ap in rows:
            por_competencia[ap.competencia][ap.tipo] = ap

        resultado: list[ApuracaoTrimestreLp] = []
        for competencia in sorted(por_competencia):
            tris = por_competencia[competencia]
            if "irpj" not in tris or "csll" not in tris:
                # Trimestre incompleto — service decide se aborta ou ignora.
                continue
            irpj_snap = parse_apuracao_output(
                "irpj", tris["irpj"].output_jsonb,
                input_jsonb=tris["irpj"].input_jsonb,
            )
            csll_snap = parse_apuracao_output(
                "csll", tris["csll"].output_jsonb,
                input_jsonb=tris["csll"].input_jsonb,
            )
            assert isinstance(irpj_snap, IrpjLpSnapshot), (
                f"Esperado IrpjLpSnapshot, recebido {type(irpj_snap).__name__}"
            )
            assert isinstance(csll_snap, CsllLpSnapshot), (
                f"Esperado CsllLpSnapshot, recebido {type(csll_snap).__name__}"
            )
            resultado.append(
                ApuracaoTrimestreLp(
                    numero=_numero_trimestre(competencia),
                    irpj=irpj_snap,
                    csll=csll_snap,
                    competencia=competencia,
                )
            )
        return resultado


class SaldosTrimestreParaEcfRepo:
    """Saldo final por conta no fim de cada trimestre, agregando os 3 meses."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def saldos_no_trimestre(
        self, empresa_id: UUID, ano: int, numero_trimestre: int
    ) -> list[SaldoTrimestreConta]:
        """Para cada conta com movimento, devolve saldo final no fim do
        trimestre + débitos/créditos acumulados nos 3 meses.

        Critério: pega o ``saldo_conta_mes`` do último mês do trimestre
        como ``saldo_final``; ``saldo_inicial`` é o do primeiro mês do
        trimestre (ou 0 se inexistente); débitos/créditos somados.
        """
        meses_trimestre = _meses_do_trimestre(ano, numero_trimestre)
        stmt = (
            select(SaldoContaMes, ContaContabil)
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia.in_(meses_trimestre))
            .order_by(
                asc(SaldoContaMes.conta_contabil_id),
                asc(SaldoContaMes.competencia),
            )
        )
        rows = (await self._s.execute(stmt)).all()

        por_conta: dict[UUID, list[tuple[SaldoContaMes, ContaContabil]]] = defaultdict(list)
        for saldo, conta in rows:
            por_conta[conta.id].append((saldo, conta))

        resultado: list[SaldoTrimestreConta] = []
        for items in por_conta.values():
            primeiro, _ = items[0]
            ultimo, conta_ultima = items[-1]
            debitos = sum(
                (s.total_debitos for s, _ in items), Decimal("0")
            )
            creditos = sum(
                (s.total_creditos for s, _ in items), Decimal("0")
            )
            resultado.append(
                SaldoTrimestreConta(
                    conta=conta_ultima,
                    debitos_acumulados=debitos,
                    creditos_acumulados=creditos,
                    saldo_inicial=primeiro.saldo_inicial,
                    saldo_final=ultimo.saldo_final,
                )
            )
        # Ordem determinística por código.
        resultado.sort(key=lambda x: x.conta.codigo)
        return resultado


class EcdVinculadaRepo:
    """Localiza a ECD ativa do mesmo ano (preenche C040 da ECF)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_ano(self, empresa_id: UUID, ano: int) -> ArquivoSped | None:
        ini = date(ano, 1, 1)
        fim = date(ano, 12, 31)
        stmt = select(ArquivoSped).where(
            and_(
                ArquivoSped.empresa_id == empresa_id,
                ArquivoSped.tipo == "ecd",
                ArquivoSped.periodo_inicio == ini,
                ArquivoSped.periodo_fim == fim,
                ArquivoSped.superseded_by.is_(None),
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


# ── Helpers ────────────────────────────────────────────────────────────────


def _numero_trimestre(competencia: date) -> int:
    """01-jan → 1; 01-abr → 2; 01-jul → 3; 01-out → 4."""
    return ((competencia.month - 1) // 3) + 1


def _meses_do_trimestre(ano: int, numero: int) -> list[date]:
    """3 competências (1º dia de cada mês) do trimestre civil informado."""
    base = 3 * (numero - 1) + 1
    return [date(ano, base, 1), date(ano, base + 1, 1), date(ano, base + 2, 1)]
