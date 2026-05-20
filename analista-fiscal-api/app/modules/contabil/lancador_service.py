"""Orquestrador do motor de lançamentos automáticos (Sprint 9 PR2).

Lista fatos de uma competência ainda não lançados, monta partidas via
``lancador_auto`` e persiste lançamentos em status='confirmado'. Idempotente
por UNIQUE parcial em ``(origem_tipo, origem_id)``.

Estratégia:
  1. Carrega ``ContasAuto`` resolvendo códigos do plano referencial.
  2. Lista fatos do período (ex.: ``DocumentoFiscal`` autorizada).
  3. Para cada fato, checa se já existe lançamento via ``LancamentoRepo.por_origem``.
  4. Se não, chama o conversor puro, persiste cabeçalho + partidas, marca
     status='confirmado'.

Princípios:
  * §8.8 — algoritmo é puro Python.
  * §8.9 — UNIQUE parcial garante idempotência completa.
  * §8.10 — log estruturado com totais por tipo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.lancador_auto import (
    ALGORITMO_VERSAO,
    ContasAuto,
    DepreciacaoFatoView,
    LancamentoCandidato,
    NfFatoView,
    ProvisaoFatoView,
    TransacaoFatoView,
    gerar_partidas_de_depreciacao,
    gerar_partidas_de_nfe,
    gerar_partidas_de_provisao,
    gerar_partidas_de_transacao,
)
from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
)
from app.modules.contabil.repo import (
    ContaContabilRepo,
    LancamentoRepo,
    PartidaRepo,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import (
    DepreciacaoMensal,
    DocumentoFiscal,
    ProvisaoMensal,
    TransacaoBancaria,
)
from app.shared.exceptions import EmpresaNaoEncontrada, PlanoContasIncompleto

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LoteResultado:
    competencia: date
    fatos_avaliados: int
    lancamentos_criados: int
    lancamentos_existentes: int
    fatos_pulados: int  # zero/sem partidas
    algoritmo_versao: str = ALGORITMO_VERSAO


class LancadorService:
    # ── Resolução do plano padrão ────────────────────────────────────────────

    async def resolver_contas(
        self, session: AsyncSession, empresa_id: uuid.UUID, em: date
    ) -> ContasAuto:
        """Resolve cada chave de CODIGOS_PADRAO_LANCAMENTO_AUTO → UUID da conta."""
        repo = ContaContabilRepo(session)
        ids: dict[str, uuid.UUID] = {}
        faltando: list[str] = []
        for chave, codigo in CODIGOS_PADRAO_LANCAMENTO_AUTO.items():
            conta = await repo.por_codigo(empresa_id, codigo, em=em)
            if conta is None or not conta.aceita_lancamento:
                faltando.append(f"{chave}({codigo})")
                continue
            ids[chave] = conta.id

        if faltando:
            raise PlanoContasIncompleto(
                f"Plano de contas incompleto para motor automático. "
                f"Ausentes: {', '.join(faltando)}. "
                f"Clone o plano referencial primeiro."
            )

        return ContasAuto(
            clientes=ids["clientes"],
            fornecedores=ids["fornecedores"],
            banco=ids["banco"],
            receita_servicos=ids["receita_servicos"],
            receita_vendas=ids["receita_vendas"],
            outras_receitas=ids["outras_receitas"],
            outras_despesas=ids["outras_despesas"],
            despesa_depreciacao=ids["despesa_depreciacao"],
            depreciacao_acumulada=ids["depreciacao_acumulada"],
            despesa_pessoal=ids["despesa_pessoal"],
            encargos_sociais=ids["encargos_sociais"],
            provisao_ferias=ids["provisao_ferias"],
            provisao_13=ids["provisao_13"],
            inss_recolher=ids["inss_recolher"],
            fgts_recolher=ids["fgts_recolher"],
        )

    # ── Lotes por tipo de fato ───────────────────────────────────────────────

    async def lote_nfe(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> LoteResultado:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        contas = await self.resolver_contas(session, empresa_id, comp_mes1)

        from datetime import datetime as _dt

        # ``emitida_em`` é TIMESTAMP — comparamos com datetime no início do mês
        # e do mês seguinte para fechar a janela [início, fim).
        ini = _dt.combine(comp_mes1, _dt.min.time())
        fim = _dt.combine(_proximo_mes(comp_mes1), _dt.min.time())
        stmt = (
            select(DocumentoFiscal)
            .where(DocumentoFiscal.empresa_id == empresa_id)
            .where(DocumentoFiscal.status != "cancelada")
            .where(
                and_(
                    DocumentoFiscal.emitida_em >= ini,
                    DocumentoFiscal.emitida_em < fim,
                )
            )
        )
        nfs = (await session.execute(stmt)).scalars().all()

        criados = 0
        existentes = 0
        pulados = 0
        for nf in nfs:
            view = NfFatoView(
                id=nf.id,
                tipo=nf.tipo,
                direcao=nf.direcao,  # type: ignore[arg-type]
                valor_total=nf.valor_total,
                emitida_em=nf.emitida_em,
                numero=nf.numero,
            )
            candidato = gerar_partidas_de_nfe(view, contas)
            criou = await self._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if criou is None:
                pulados += 1
            elif criou:
                criados += 1
            else:
                existentes += 1

        await session.commit()
        log.info(
            "contabil.auto.nfe",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            avaliados=len(nfs),
            criados=criados,
            existentes=existentes,
            pulados=pulados,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=len(nfs),
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
        )

    async def lote_transacao(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> LoteResultado:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        contas = await self.resolver_contas(session, empresa_id, comp_mes1)

        proximo_mes = _proximo_mes(comp_mes1)
        stmt = (
            select(TransacaoBancaria)
            .where(TransacaoBancaria.empresa_id == empresa_id)
            .where(TransacaoBancaria.status == "CONFIRMED")
            .where(
                and_(
                    TransacaoBancaria.data_transacao >= comp_mes1,
                    TransacaoBancaria.data_transacao < proximo_mes,
                )
            )
        )
        txs = (await session.execute(stmt)).scalars().all()

        criados = 0
        existentes = 0
        pulados = 0
        for tx in txs:
            view = TransacaoFatoView(
                id=tx.id,
                valor=tx.valor,
                tipo=tx.tipo,  # type: ignore[arg-type]
                data_transacao=tx.data_transacao,
                descricao=tx.descricao,
            )
            candidato = gerar_partidas_de_transacao(view, contas)
            criou = await self._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if criou is None:
                pulados += 1
            elif criou:
                criados += 1
            else:
                existentes += 1

        await session.commit()
        log.info(
            "contabil.auto.transacao",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            criados=criados,
            existentes=existentes,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=len(txs),
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
        )

    async def lote_depreciacao(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> LoteResultado:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        contas = await self.resolver_contas(session, empresa_id, comp_mes1)

        # join via bem_imobilizado.empresa_id (DepreciacaoMensal só tem tenant)
        from app.shared.db.models import BemImobilizado

        stmt = (
            select(DepreciacaoMensal)
            .join(BemImobilizado, BemImobilizado.id == DepreciacaoMensal.bem_id)
            .where(BemImobilizado.empresa_id == empresa_id)
            .where(DepreciacaoMensal.competencia == comp_mes1)
        )
        deprs = (await session.execute(stmt)).scalars().all()

        criados = 0
        existentes = 0
        pulados = 0
        for d in deprs:
            view = DepreciacaoFatoView(
                id=d.id,
                competencia=d.competencia,
                valor_depreciado=d.valor_depreciado,
            )
            candidato = gerar_partidas_de_depreciacao(view, contas)
            if candidato is None:
                pulados += 1
                continue
            criou = await self._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if criou:
                criados += 1
            else:
                existentes += 1

        await session.commit()
        log.info(
            "contabil.auto.depreciacao",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            criados=criados,
            existentes=existentes,
            pulados=pulados,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=len(deprs),
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
        )

    async def lote_provisao(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> LoteResultado:
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        contas = await self.resolver_contas(session, empresa_id, comp_mes1)

        stmt = (
            select(ProvisaoMensal)
            .where(ProvisaoMensal.empresa_id == empresa_id)
            .where(ProvisaoMensal.competencia == comp_mes1)
        )
        provs = (await session.execute(stmt)).scalars().all()

        criados = 0
        existentes = 0
        pulados = 0
        for p in provs:
            view = ProvisaoFatoView(
                id=p.id,
                competencia=p.competencia,
                tipo=p.tipo,
                valor_provisao=p.valor_provisao,
            )
            candidato = gerar_partidas_de_provisao(view, contas)
            if candidato is None:
                pulados += 1
                continue
            criou = await self._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if criou:
                criados += 1
            else:
                existentes += 1

        await session.commit()
        log.info(
            "contabil.auto.provisao",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            criados=criados,
            existentes=existentes,
            pulados=pulados,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=len(provs),
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
        )

    # ── helpers privados ─────────────────────────────────────────────────────

    async def _garantir_empresa(
        self, session: AsyncSession, empresa_id: uuid.UUID
    ) -> None:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

    async def _persistir(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        candidato: LancamentoCandidato,
    ) -> bool | None:
        """Persiste lançamento em status='confirmado'. Retorna:
          * True  → criado novo
          * False → já existia (idempotente)
          * None  → não houve partidas (não deveria acontecer aqui)
        """
        if not candidato.partidas:
            return None

        lanc_repo = LancamentoRepo(session)
        existente = await lanc_repo.por_origem(
            candidato.origem_tipo, candidato.origem_id
        )
        if existente is not None:
            return False

        total = candidato.total
        lanc = await lanc_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            data_lancamento=candidato.data_lancamento,
            competencia=candidato.competencia,
            historico=candidato.historico,
            origem_tipo=candidato.origem_tipo,
            origem_id=candidato.origem_id,
            total_debito=total,
            total_credito=total,
            status="confirmado",
        )
        await PartidaRepo(session).criar_lote(
            tenant_id=tenant_id,
            lancamento_id=lanc.id,
            partidas=[(p.conta_id, p.tipo, p.valor) for p in candidato.partidas],
        )
        return True


def _proximo_mes(comp: date) -> date:
    if comp.month == 12:
        return date(comp.year + 1, 1, 1)
    return date(comp.year, comp.month + 1, 1)
