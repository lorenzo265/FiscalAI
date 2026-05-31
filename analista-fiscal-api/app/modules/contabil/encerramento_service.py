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
  4. Sprint 18 PR1: chama ``abrir_exercicio(ano+1)`` automaticamente para
     transportar saldos patrimoniais e zerar contas de resultado em
     janeiro do próximo ano (pendência #8 resolvida).

Abertura de exercício (Sprint 18 PR1):
  * ``abrir_exercicio(ano)`` materializa ``saldo_conta_mes`` de janeiro/ano
    com ``saldo_inicial = saldo_final(dezembro/ano-1)`` para contas
    patrimoniais e ``0`` para receita/despesa. Idempotente via UNIQUE
    natural de ``saldo_conta_mes`` + ON CONFLICT DO NOTHING.
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
    ContaContabil,
    LancamentoContabil,
    SaldoContaMes,
)
from app.shared.exceptions import (
    CompetenciaJaEncerrada,
    EmpresaNaoEncontrada,
    EncerramentoMensalAusente,
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


@dataclass(frozen=True, slots=True)
class AberturaExercicioResultado:
    """Resultado da reabertura de exercício (Sprint 18 PR1 — pendência #8).

    Transporte de saldos patrimoniais de dezembro/ano-1 para janeiro/ano e
    zeragem das contas de resultado. ``saldo_total_transportado`` é a
    soma absoluta dos saldos patrimoniais — útil para audit.
    """

    ano: int
    contas_patrimoniais: int
    contas_resultado: int
    saldo_total_transportado: Decimal


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
        """Bulk INSERT ... ON CONFLICT DO UPDATE — idempotente, 1 round-trip ao DB.

        Antes era 1 execute por linha (N round-trips para ~36 contas).
        """
        if not linhas:
            return 0

        valores = [
            {
                "tenant_id": tenant_id,
                "empresa_id": empresa_id,
                "conta_contabil_id": linha.conta_id,
                "competencia": competencia,
                "saldo_inicial": linha.saldo_inicial,
                "total_debitos": linha.total_debitos,
                "total_creditos": linha.total_creditos,
                "saldo_final": linha.saldo_final,
                "status": "fechado",
            }
            for linha in linhas
        ]
        base_stmt = pg_insert(SaldoContaMes).values(valores)
        upsert_stmt = base_stmt.on_conflict_do_update(
            constraint="uq_saldo_empresa_conta_comp",
            set_={
                "saldo_inicial": base_stmt.excluded.saldo_inicial,
                "total_debitos": base_stmt.excluded.total_debitos,
                "total_creditos": base_stmt.excluded.total_creditos,
                "saldo_final": base_stmt.excluded.saldo_final,
                "status": base_stmt.excluded.status,
            },
        ).returning(SaldoContaMes.id)
        rows = (await session.execute(upsert_stmt)).all()
        return len(rows)

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
            raise EncerramentoMensalAusente(
                f"Saldos de dezembro/{ano} ausentes — encerre o mês primeiro"
            )

        # Carrega metadata das contas em uma só query.
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

        # ``saldo_final`` em ``relatorios.calcular_saldo_final`` é signed pela
        # natureza: receita (nat. C) positiva = mais créditos que débitos; se
        # estornos > vendas, vira negativa e representa "perda em receita".
        # Para zerar contra 3.9.01, lança o oposto da natureza pela valor absoluto.
        for r in rows:
            conta = contas_por_id.get(r.conta_contabil_id)
            if conta is None:
                continue
            saldo = Decimal(str(r.saldo_final))
            if saldo == Decimal("0"):
                continue
            valor_abs = saldo.copy_abs()
            if conta.tipo == "receita":
                # Saldo positivo (C) → zera com D. Saldo negativo (inversão) → zera com C.
                tipo = "D" if saldo > 0 else "C"
                partidas.append((conta.id, tipo, valor_abs))
                receitas_total += saldo  # signed — preserva sinal no líquido
            elif conta.tipo == "despesa":
                # Saldo positivo (D) → zera com C. Saldo negativo (recuperação) → zera com D.
                tipo = "C" if saldo > 0 else "D"
                partidas.append((conta.id, tipo, valor_abs))
                despesas_total += saldo  # signed

        # Resultado líquido vai para 3.9.01.
        resultado = receitas_total - despesas_total
        if resultado > Decimal("0"):
            # Lucro: 3.9.01 é C (PL); recebe crédito.
            partidas.append((resultado_conta.id, "C", resultado))
        elif resultado < Decimal("0"):
            # Prejuízo: 3.9.01 recebe débito.
            partidas.append((resultado_conta.id, "D", resultado.copy_abs()))
        else:
            # Resultado zero — não há nada para apurar, mas ainda abrimos
            # o exercício seguinte para transportar saldos patrimoniais.
            await self.abrir_exercicio(session, tenant_id, empresa_id, ano + 1)
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
            # Re-chamada — garante que abertura também foi disparada.
            await self.abrir_exercicio(session, tenant_id, empresa_id, ano + 1)
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

        # Sprint 18 PR1: dispara abertura do exercício seguinte (pendência #8).
        # Transporta saldos patrimoniais e zera contas de resultado em janeiro/ano+1.
        # Falha silenciosa? Não — abertura é idempotente; deixar exceção subir.
        await self.abrir_exercicio(session, tenant_id, empresa_id, ano + 1)

        return EncerramentoAnualResultado(
            ano=ano,
            receitas_zeradas=receitas_total,
            despesas_zeradas=despesas_total,
            resultado_exercicio=resultado,
            lancamento_apuracao_id=lancamento.id,
        )

    # ── Abertura do exercício seguinte (Sprint 18 PR1) ──────────────────────

    async def abrir_exercicio(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        ano: int,
    ) -> AberturaExercicioResultado:
        """Materializa saldos iniciais de janeiro/ano (pendência #8).

        Para cada conta com saldo em dezembro/ano-1:

          * Patrimonial (``ativo``, ``passivo``, ``patrimonio_liquido``,
            ``conta_resultado``) → ``saldo_inicial(janeiro/ano)`` =
            ``saldo_final(dezembro/ano-1)``.
          * Resultado (``receita``, ``despesa``) → ``saldo_inicial = 0``.

        Idempotente via UNIQUE (empresa_id, conta_contabil_id, competencia)
        em ``saldo_conta_mes`` + ON CONFLICT DO NOTHING. Re-execução é
        no-op (preserva ``saldo_conta_mes`` que já tenha movimento de
        janeiro registrado).

        Pré-condição: dezembro/ano-1 deve estar encerrado (``status='fechado'``
        em pelo menos uma linha de saldo). Sem isso, levanta
        ``EncerramentoMensalAusente``.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        dezembro_anterior = date(ano - 1, 12, 1)
        janeiro = date(ano, 1, 1)

        # Pré-condição: dezembro do ano anterior deve estar encerrado.
        fechado = (
            await session.execute(
                select(SaldoContaMes.id)
                .where(
                    SaldoContaMes.empresa_id == empresa_id,
                    SaldoContaMes.competencia == dezembro_anterior,
                    SaldoContaMes.status == "fechado",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if fechado is None:
            raise EncerramentoMensalAusente(
                f"Dezembro/{ano - 1} ausente — encerre antes de abrir {ano}"
            )

        # Junta saldo_final com tipo da conta em uma única query.
        stmt = (
            select(
                SaldoContaMes.conta_contabil_id,
                SaldoContaMes.saldo_final,
                ContaContabil.tipo,
            )
            .join(
                ContaContabil,
                ContaContabil.id == SaldoContaMes.conta_contabil_id,
            )
            .where(
                SaldoContaMes.empresa_id == empresa_id,
                SaldoContaMes.competencia == dezembro_anterior,
            )
        )
        rows = (await session.execute(stmt)).all()

        patrimonial = {"ativo", "passivo", "patrimonio_liquido", "conta_resultado"}

        valores: list[dict[str, object]] = []
        contas_patrimoniais = 0
        contas_resultado = 0
        saldo_total_transportado = Decimal("0")

        for r in rows:
            if r.tipo in patrimonial:
                saldo_inicial = Decimal(str(r.saldo_final))
                contas_patrimoniais += 1
                saldo_total_transportado += saldo_inicial.copy_abs()
            else:
                saldo_inicial = Decimal("0")
                contas_resultado += 1
            valores.append(
                {
                    "tenant_id": tenant_id,
                    "empresa_id": empresa_id,
                    "conta_contabil_id": r.conta_contabil_id,
                    "competencia": janeiro,
                    "saldo_inicial": saldo_inicial,
                    "total_debitos": Decimal("0"),
                    "total_creditos": Decimal("0"),
                    "saldo_final": saldo_inicial,
                    "status": "aberto",
                }
            )

        if valores:
            base_stmt = pg_insert(SaldoContaMes).values(valores)
            # ON CONFLICT DO NOTHING preserva saldos eventualmente já calculados
            # de movimento de janeiro — só insere as contas que ainda não têm
            # linha materializada.
            stmt_upsert = base_stmt.on_conflict_do_nothing(
                index_elements=[
                    "empresa_id",
                    "conta_contabil_id",
                    "competencia",
                ]
            )
            await session.execute(stmt_upsert)
            await session.commit()

        log.info(
            "contabil.abertura.exercicio",
            empresa_id=str(empresa_id),
            ano=ano,
            contas_patrimoniais=contas_patrimoniais,
            contas_resultado=contas_resultado,
            saldo_total=str(saldo_total_transportado),
        )

        return AberturaExercicioResultado(
            ano=ano,
            contas_patrimoniais=contas_patrimoniais,
            contas_resultado=contas_resultado,
            saldo_total_transportado=saldo_total_transportado,
        )


def _origem_apuracao(empresa_id: UUID, ano: int) -> UUID:
    """UUID determinístico para o lançamento de encerramento anual.

    Permite idempotência via UNIQUE (origem_tipo, origem_id).
    """
    base = f"apuracao:{empresa_id}:{ano}"
    return _uuid_mod.uuid5(_uuid_mod.NAMESPACE_URL, base)
