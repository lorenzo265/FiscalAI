"""Encerramento mensal e anual (Sprint 9 PR3).

Mensal:
  1. Calcula saldos da competência via ``RelatoriosService.balancete``.
  2. Persiste em ``saldo_conta_mes`` (UPSERT por UNIQUE).
  3. Marca lançamentos da competência como ``status='encerrado'``.
  4. A partir daqui, novos lançamentos na mesma competência são bloqueados
     pelo service de criação (verificação no ContabilService.criar_lancamento_manual
     fica como TODO — defesa adicional além do status).

Anual:
  1. Encerra dezembro (se ainda não estiver).
  2. Apura resultado: zera contas de receita/despesa contra
     ``3.9.01 Resultado do Exercício`` via UM lançamento de encerramento.
  3. Cria saldo_conta_mes final do ano para contas de resultado em zero.
"""

from __future__ import annotations

import uuid as _uuid_mod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.relatorios import LinhaBalancete
from app.modules.contabil.relatorios_service import RelatoriosService
from app.modules.contabil.repo import (
    ContaContabilRepo,
    LancamentoRepo,
    PartidaRepo,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import (
    LancamentoContabil,
    SaldoContaMes,
)
from app.shared.exceptions import (
    CompetenciaJaEncerrada,
    EmpresaNaoEncontrada,
    PlanoContasIncompleto,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EncerramentoMensalResultado:
    competencia: date
    saldos_persistidos: int
    lancamentos_encerrados: int


@dataclass(frozen=True, slots=True)
class EncerramentoAnualResultado:
    ano: int
    receitas_zeradas: Decimal
    despesas_zeradas: Decimal
    resultado_exercicio: Decimal  # signed: positivo = lucro; negativo = prejuízo
    lancamento_apuracao_id: UUID


class EncerramentoService:
    # ── Mensal ───────────────────────────────────────────────────────────────

    async def encerrar_mes(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
    ) -> EncerramentoMensalResultado:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        comp_mes1 = date(competencia.year, competencia.month, 1)

        # Bloqueia re-encerramento.
        ja_fechado = (
            await session.execute(
                select(SaldoContaMes.id).where(
                    SaldoContaMes.empresa_id == empresa_id,
                    SaldoContaMes.competencia == comp_mes1,
                    SaldoContaMes.status == "fechado",
                ).limit(1)
            )
        ).scalar_one_or_none()
        if ja_fechado is not None:
            raise CompetenciaJaEncerrada(
                f"Competência {comp_mes1:%Y-%m} já encerrada"
            )

        # Balancete vigente.
        linhas = await RelatoriosService().balancete(session, empresa_id, comp_mes1)

        # Persiste cada saldo.
        saldos_persistidos = await self._upsert_saldos(
            session, tenant_id, empresa_id, comp_mes1, linhas
        )

        # Trava lançamentos do mês.
        upd = (
            update(LancamentoContabil)
            .where(
                LancamentoContabil.empresa_id == empresa_id,
                LancamentoContabil.competencia == comp_mes1,
                LancamentoContabil.status == "confirmado",
            )
            .values(status="encerrado")
        )
        result = await session.execute(upd)
        await session.commit()

        rowcount = int(getattr(result, "rowcount", 0) or 0)
        log.info(
            "contabil.encerramento.mensal",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            saldos=saldos_persistidos,
            lancamentos=rowcount,
        )
        return EncerramentoMensalResultado(
            competencia=comp_mes1,
            saldos_persistidos=saldos_persistidos,
            lancamentos_encerrados=rowcount,
        )

    async def _upsert_saldos(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
        linhas: list[LinhaBalancete],
    ) -> int:
        """ON CONFLICT DO UPDATE para tornar a operação idempotente."""
        persistidos = 0
        for linha in linhas:
            stmt = (
                pg_insert(SaldoContaMes)
                .values(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                    conta_contabil_id=linha.conta_id,
                    competencia=competencia,
                    saldo_inicial=linha.saldo_inicial,
                    total_debitos=linha.total_debitos,
                    total_creditos=linha.total_creditos,
                    saldo_final=linha.saldo_final,
                    status="fechado",
                )
                .on_conflict_do_update(
                    constraint="uq_saldo_empresa_conta_comp",
                    set_={
                        "saldo_inicial": linha.saldo_inicial,
                        "total_debitos": linha.total_debitos,
                        "total_creditos": linha.total_creditos,
                        "saldo_final": linha.saldo_final,
                        "status": "fechado",
                    },
                )
                .returning(SaldoContaMes.id)
            )
            await session.execute(stmt)
            persistidos += 1
        return persistidos

    # ── Anual ────────────────────────────────────────────────────────────────

    async def encerrar_ano(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        ano: int,
    ) -> EncerramentoAnualResultado:
        """Zera contas de resultado contra "Resultado do Exercício".

        Geração de um lançamento ÚNICO com várias partidas:
          * D em cada conta de receita até zerar seu saldo (saldo crédito → débito).
          * C em cada conta de despesa até zerar (saldo débito → crédito).
          * Contrapartida líquida em 3.9.01 (Resultado do Exercício).
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        dezembro = date(ano, 12, 1)
        # Recupera saldos finais de dezembro para contas de receita/despesa.
        stmt = (
            select(
                SaldoContaMes.conta_contabil_id,
                SaldoContaMes.saldo_final,
            )
            .where(
                SaldoContaMes.empresa_id == empresa_id,
                SaldoContaMes.competencia == dezembro,
            )
        )
        rows = (await session.execute(stmt)).all()
        if not rows:
            raise CompetenciaJaEncerrada(
                f"Saldos de dezembro/{ano} ausentes — encerre o mês primeiro"
            )

        # Carrega metadata das contas em uma só query.
        from app.shared.db.models import ContaContabil

        ids_contas = [r.conta_contabil_id for r in rows]
        contas_rows = (
            await session.execute(
                select(ContaContabil).where(ContaContabil.id.in_(ids_contas))
            )
        ).scalars().all()
        contas_por_id = {c.id: c for c in contas_rows}

        # Resolve 3.9.01 Resultado do Exercício
        resultado_conta = await ContaContabilRepo(session).por_codigo(
            empresa_id, "3.9.01", em=dezembro
        )
        if resultado_conta is None:
            raise PlanoContasIncompleto(
                "Conta 3.9.01 (Resultado do Exercício) não encontrada — "
                "clone o plano referencial primeiro."
            )

        receitas_total = Decimal("0")
        despesas_total = Decimal("0")
        partidas: list[tuple[UUID, str, Decimal]] = []

        for r in rows:
            conta = contas_por_id.get(r.conta_contabil_id)
            if conta is None:
                continue
            saldo = Decimal(str(r.saldo_final))
            if saldo <= Decimal("0"):
                continue
            if conta.tipo == "receita":
                # Receita tem natureza C — saldo positivo C. Para zerar, lança D.
                partidas.append((conta.id, "D", saldo))
                receitas_total += saldo
            elif conta.tipo == "despesa":
                # Despesa tem natureza D — saldo positivo D. Para zerar, lança C.
                partidas.append((conta.id, "C", saldo))
                despesas_total += saldo

        # Resultado líquido vai para 3.9.01.
        resultado = receitas_total - despesas_total
        if resultado > Decimal("0"):
            # Lucro: 3.9.01 é C (PL); recebe crédito.
            partidas.append((resultado_conta.id, "C", resultado))
        elif resultado < Decimal("0"):
            # Prejuízo: 3.9.01 recebe débito.
            partidas.append((resultado_conta.id, "D", resultado.copy_abs()))
        else:
            # Resultado zero — não há nada para apurar.
            return EncerramentoAnualResultado(
                ano=ano,
                receitas_zeradas=receitas_total,
                despesas_zeradas=despesas_total,
                resultado_exercicio=Decimal("0"),
                lancamento_apuracao_id=UUID(int=0),
            )

        total = sum((v for (_c, t, v) in partidas if t == "D"), start=Decimal("0"))
        origem_id = _origem_apuracao(empresa_id, ano)

        # Checa idempotência via origem_tipo='encerramento'.
        lanc_repo = LancamentoRepo(session)
        existente = await lanc_repo.por_origem("encerramento", origem_id)
        if existente is not None:
            return EncerramentoAnualResultado(
                ano=ano,
                receitas_zeradas=receitas_total,
                despesas_zeradas=despesas_total,
                resultado_exercicio=resultado,
                lancamento_apuracao_id=existente.id,
            )

        lancamento = await lanc_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            data_lancamento=date(ano, 12, 31),
            competencia=dezembro,
            historico=f"Apuração do resultado do exercício {ano}",
            origem_tipo="encerramento",
            origem_id=origem_id,
            total_debito=total,
            total_credito=total,
            status="encerrado",
        )
        await PartidaRepo(session).criar_lote(
            tenant_id=tenant_id,
            lancamento_id=lancamento.id,
            partidas=partidas,
        )
        await session.commit()

        log.info(
            "contabil.encerramento.anual",
            empresa_id=str(empresa_id),
            ano=ano,
            receitas=str(receitas_total),
            despesas=str(despesas_total),
            resultado=str(resultado),
            lancamento_id=str(lancamento.id),
        )
        return EncerramentoAnualResultado(
            ano=ano,
            receitas_zeradas=receitas_total,
            despesas_zeradas=despesas_total,
            resultado_exercicio=resultado,
            lancamento_apuracao_id=lancamento.id,
        )


def _origem_apuracao(empresa_id: UUID, ano: int) -> UUID:
    """UUID determinístico para o lançamento de encerramento anual.

    Permite idempotência via UNIQUE (origem_tipo, origem_id).
    """
    base = f"apuracao:{empresa_id}:{ano}"
    return _uuid_mod.uuid5(_uuid_mod.NAMESPACE_URL, base)
