"""Repositórios — relatórios contábeis (Sprint 12 PR1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fiscal.snapshots import parse_apuracao_output
from app.modules.relatorios.calcula_balanco import (
    SaldoConta as SaldoContaBalanco,
)
from app.modules.relatorios.calcula_dre import SaldoConta
from app.shared.db.models import (
    ApuracaoFiscal,
    ContaContabil,
    RelatorioGerado,
    SaldoContaMes,
)


@dataclass(frozen=True, slots=True)
class _MovimentoPeriodo:
    """Movimento acumulado de uma conta de resultado num período."""

    codigo: str
    descricao: str
    movimento: Decimal  # signed pela natureza (positivo = sinal padrão)


class SaldosPeriodoRepo:
    """Consulta saldos de contas de resultado (4.x e 5.x) num período.

    Para contas de resultado o movimento do período = soma de
    (total_creditos − total_debitos) × sinal_natureza ao longo dos meses.
    Não usamos saldo_final porque o encerramento anual zera essas contas
    e perderíamos a info ao cruzar fim de exercício.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def movimento_resultado_periodo(
        self, empresa_id: UUID, periodo_inicio: date, periodo_fim: date
    ) -> list[SaldoConta]:
        """Retorna o movimento acumulado das contas 4.x e 5.x no período.

        ``movimento`` vem positivo na natureza padrão da conta (positivo em
        4.x = receita realizada; positivo em 5.x = despesa incorrida).
        """
        # Σ creditos − debitos por conta no período, depois aplica sinal da natureza.
        delta_credito = func.sum(
            SaldoContaMes.total_creditos - SaldoContaMes.total_debitos
        )

        stmt = (
            select(
                ContaContabil.codigo,
                ContaContabil.descricao,
                ContaContabil.natureza,
                delta_credito.label("delta"),
            )
            .select_from(SaldoContaMes)
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia >= periodo_inicio)
            .where(SaldoContaMes.competencia <= periodo_fim)
            .where(ContaContabil.aceita_lancamento.is_(True))
            .where(ContaContabil.tipo.in_(("receita", "despesa")))
            .group_by(
                ContaContabil.codigo,
                ContaContabil.descricao,
                ContaContabil.natureza,
            )
        )

        rows = (await self._s.execute(stmt)).all()

        saldos: list[SaldoConta] = []
        for codigo, descricao, natureza, delta in rows:
            d = delta or Decimal("0")
            # Receita (natureza C): movimento positivo = créditos > débitos.
            # Despesa (natureza D): movimento positivo = débitos > créditos
            #   → invertemos o sinal de "creditos − debitos".
            valor = d if natureza == "C" else -d
            saldos.append(
                SaldoConta(
                    codigo=codigo,
                    descricao=descricao,
                    saldo_final=valor,
                )
            )
        return saldos

    async def saldos_posicao_em(
        self, empresa_id: UUID, data_referencia: date
    ) -> list[SaldoContaBalanco]:
        """Saldo final de cada conta analítica de Ativo/Passivo/PL.

        Para cada conta, pega a linha mais recente em ``saldo_conta_mes``
        com ``competencia <= data_referencia``. Aplica sinal pela natureza
        ao expor (positivo = posição alinhada).
        """
        from sqlalchemy import and_

        # Subquery: última competencia por conta <= data_referencia
        ult = (
            select(
                SaldoContaMes.conta_contabil_id.label("cid"),
                func.max(SaldoContaMes.competencia).label("ult_comp"),
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia <= data_referencia)
            .group_by(SaldoContaMes.conta_contabil_id)
            .subquery()
        )

        stmt = (
            select(
                ContaContabil.codigo,
                ContaContabil.descricao,
                ContaContabil.natureza,
                ContaContabil.tipo,
                SaldoContaMes.saldo_final,
            )
            .select_from(SaldoContaMes)
            .join(
                ult,
                and_(
                    SaldoContaMes.conta_contabil_id == ult.c.cid,
                    SaldoContaMes.competencia == ult.c.ult_comp,
                ),
            )
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(ContaContabil.aceita_lancamento.is_(True))
            .where(
                ContaContabil.tipo.in_(
                    ("ativo", "passivo", "patrimonio_liquido")
                )
            )
        )

        rows = (await self._s.execute(stmt)).all()
        return [
            SaldoContaBalanco(
                codigo=codigo,
                descricao=descricao,
                natureza=natureza,
                tipo=tipo,
                saldo_final=saldo,
            )
            for codigo, descricao, natureza, tipo, saldo in rows
        ]

    async def saldo_conta_codigo_em(
        self, empresa_id: UUID, codigo: str, data_referencia: date
    ) -> Decimal:
        """Saldo final (signed pela natureza) de UMA conta na data."""
        saldos = await self.saldos_posicao_em(empresa_id, data_referencia)
        for s in saldos:
            if s.codigo == codigo:
                return s.saldo_final
        return Decimal("0")

    async def soma_movimento_codigo_periodo(
        self,
        empresa_id: UUID,
        codigo: str,
        periodo_inicio: date,
        periodo_fim: date,
    ) -> Decimal:
        """Soma de débitos − créditos (signed pela natureza) de uma conta
        no período. Útil para depreciação acumulada/provisões constituídas."""
        delta_credito = func.sum(
            SaldoContaMes.total_creditos - SaldoContaMes.total_debitos
        )
        stmt = (
            select(
                ContaContabil.natureza,
                delta_credito.label("delta"),
            )
            .select_from(SaldoContaMes)
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(SaldoContaMes.empresa_id == empresa_id)
            .where(SaldoContaMes.competencia >= periodo_inicio)
            .where(SaldoContaMes.competencia <= periodo_fim)
            .where(ContaContabil.codigo == codigo)
            .group_by(ContaContabil.natureza)
        )
        row = (await self._s.execute(stmt)).first()
        if row is None:
            return Decimal("0")
        natureza, delta = row
        d = delta or Decimal("0")
        return d if natureza == "C" else -d

    async def irpj_csll_apurado_no_periodo(
        self, empresa_id: UUID, periodo_inicio: date, periodo_fim: date
    ) -> Decimal:
        """Soma IRPJ + CSLL apurados (Sprint 11 PR1) no período.

        Para DRE: usa `valor_devido` (= IRPJ bruto + CSLL) — a despesa
        accrued no período, não o caixa efetivo. IRRF compensado é ativo
        a recuperar, não reduz a despesa contábil de IRPJ.
        """
        stmt = select(ApuracaoFiscal).where(
            ApuracaoFiscal.empresa_id == empresa_id,
            ApuracaoFiscal.competencia >= periodo_inicio,
            ApuracaoFiscal.competencia <= periodo_fim,
            ApuracaoFiscal.tipo.in_(("irpj", "csll")),
        )
        total = Decimal("0")
        for ap in (await self._s.execute(stmt)).scalars().all():
            snap = parse_apuracao_output(
                ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb,
            )
            total += snap.valor_devido
        return total

    async def apuracoes_do_trimestre(
        self, empresa_id: UUID, periodo_inicio: date, periodo_fim: date
    ) -> list[ApuracaoFiscal]:
        """Lista todas as apurações fiscais persistidas no período (Sprint 11).

        Inclui IRPJ + CSLL trimestrais, PIS + Cofins mensais, ICMS, ISS, etc.
        Usado pelo ``calcula_dre_aux_lp`` para montar a reconciliação.
        """
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia >= periodo_inicio)
            .where(ApuracaoFiscal.competencia <= periodo_fim)
            .order_by(ApuracaoFiscal.competencia, ApuracaoFiscal.tipo)
        )
        return list((await self._s.execute(stmt)).scalars().all())


class RelatorioRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, relatorio_id: UUID) -> RelatorioGerado | None:
        stmt = select(RelatorioGerado).where(RelatorioGerado.id == relatorio_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def ativo(
        self,
        empresa_id: UUID,
        tipo: str,
        periodo_inicio: date,
        periodo_fim: date,
    ) -> RelatorioGerado | None:
        """Retorna a versão ativa (não superseded) do (empresa, tipo, período)."""
        stmt = select(RelatorioGerado).where(
            RelatorioGerado.empresa_id == empresa_id,
            RelatorioGerado.tipo == tipo,
            RelatorioGerado.periodo_inicio == periodo_inicio,
            RelatorioGerado.periodo_fim == periodo_fim,
            RelatorioGerado.superseded_by.is_(None),
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        somente_ativos: bool = True,
        limite: int = 50,
    ) -> list[RelatorioGerado]:
        stmt = (
            select(RelatorioGerado)
            .where(RelatorioGerado.empresa_id == empresa_id)
            .order_by(RelatorioGerado.criado_em.desc())
            .limit(limite)
        )
        if tipo:
            stmt = stmt.where(RelatorioGerado.tipo == tipo)
        if somente_ativos:
            stmt = stmt.where(RelatorioGerado.superseded_by.is_(None))
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, r: RelatorioGerado) -> RelatorioGerado:
        self._s.add(r)
        await self._s.flush()
        await self._s.refresh(r)
        return r

    async def marcar_superseded(
        self, anterior: RelatorioGerado, nova_id: UUID
    ) -> None:
        anterior.superseded_by = nova_id
        await self._s.flush()
