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
from decimal import ROUND_HALF_EVEN, Decimal

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.lancador_auto import (
    ALGORITMO_VERSAO,
    ALGORITMO_VERSAO_IMPOSTOS,
    ApuracaoFatoView,
    ContasAuto,
    ContasImpostos,
    DepreciacaoFatoView,
    FolhaFatoView,
    LancamentoCandidato,
    NfFatoView,
    ProvisaoFatoView,
    TransacaoFatoView,
    gerar_partidas_de_apuracao,
    gerar_partidas_de_depreciacao,
    gerar_partidas_de_folha,
    gerar_partidas_de_nfe,
    gerar_partidas_de_provisao,
    gerar_partidas_de_transacao,
)
from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
    _CHAVES_CORE,
    _CHAVES_IMPOSTOS,
)
from app.modules.fiscal.snapshots import parse_apuracao_output
from app.modules.contabil.repo import (
    ContaContabilRepo,
    LancamentoRepo,
    PartidaRepo,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import (
    ApuracaoFiscal,
    DepreciacaoMensal,
    DocumentoFiscal,
    FolhaMensal,
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
        """Resolve as 20 contas core → UUID.

        Itera apenas ``_CHAVES_CORE`` (conjunto fixo) em vez do dict inteiro.
        Isso garante que novas chaves adicionadas ao dict (ex.: icms_recolher,
        das_recolher) não quebrem empresas que clonaram o plano antes dessas
        contas existirem — o erro só ocorre nos lotes que de fato as exigem
        (ver ``resolver_contas_impostos``).
        """
        repo = ContaContabilRepo(session)
        ids: dict[str, uuid.UUID] = {}
        faltando: list[str] = []
        for chave in _CHAVES_CORE:
            codigo = CODIGOS_PADRAO_LANCAMENTO_AUTO[chave]
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
            # Sprint 19.7 PR1 (#10) — folha contabilizada.
            irrf_funcionarios_recolher=ids["irrf_funcionarios_recolher"],
            salarios_pagar=ids["salarios_pagar"],
            estoques=ids["estoques"],
            imobilizado=ids["imobilizado"],
            despesa_servicos=ids["despesa_servicos"],
        )

    async def resolver_contas_impostos(
        self, session: AsyncSession, empresa_id: uuid.UUID, em: date
    ) -> ContasImpostos:
        """Resolve as 9 contas de imposto → UUID.

        Separado de ``resolver_contas`` para não bloquear empresas antigas
        que não têm as contas de imposto (lotes nfe/transacao/etc. seguem
        funcionando). Só ``lote_impostos`` chama esta função.

        Levanta ``PlanoContasIncompleto`` com instrução de re-clonar quando
        qualquer uma das 9 contas estiver ausente.
        """
        repo = ContaContabilRepo(session)
        ids: dict[str, uuid.UUID] = {}
        faltando: list[str] = []
        for chave in _CHAVES_IMPOSTOS:
            codigo = CODIGOS_PADRAO_LANCAMENTO_AUTO[chave]
            conta = await repo.por_codigo(empresa_id, codigo, em=em)
            if conta is None or not conta.aceita_lancamento:
                faltando.append(f"{chave}({codigo})")
                continue
            ids[chave] = conta.id

        if faltando:
            raise PlanoContasIncompleto(
                f"Plano de contas incompleto para lançamento de impostos. "
                f"Ausentes: {', '.join(faltando)}. "
                f"Re-clone o plano referencial para adicionar as contas novas "
                f"(2.1.4.01–07, 5.1.05, 5.3.01)."
            )

        return ContasImpostos(
            das_recolher=ids["das_recolher"],
            icms_recolher=ids["icms_recolher"],
            iss_recolher=ids["iss_recolher"],
            pis_recolher=ids["pis_recolher"],
            cofins_recolher=ids["cofins_recolher"],
            irpj_recolher=ids["irpj_recolher"],
            csll_recolher=ids["csll_recolher"],
            impostos_sobre_receita=ids["impostos_sobre_receita"],
            provisao_irpj_csll=ids["provisao_irpj_csll"],
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
                cfop=nf.cfop,
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

    # ── Sprint 19.7 PR1 (#10) — folha mensal ────────────────────────────────

    async def lote_folha(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        folha: FolhaMensal,
    ) -> LoteResultado:
        """Sprint 19.7 PR1 (#10) — gera lançamento contábil de 1 folha fechada.

        Espera ``folha.status='fechada'`` (caller é ``FolhaService.fechar_folha``
        ou re-run admin). Idempotente via ``UNIQUE(origem_tipo='folha',
        origem_id=folha.id)``.
        """
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(folha.competencia.year, folha.competencia.month, 1)
        contas = await self.resolver_contas(session, empresa_id, comp_mes1)

        view = FolhaFatoView(
            id=folha.id,
            competencia=folha.competencia,
            total_proventos=folha.total_proventos,
            total_inss_empregado=folha.total_inss_empregado,
            total_irrf=folha.total_irrf,
            total_fgts_empregador=folha.total_fgts_empregador,
        )
        candidato = gerar_partidas_de_folha(view, contas)

        criados = 0
        existentes = 0
        pulados = 0
        if candidato is None:
            pulados = 1
        else:
            criou = await self._persistir(
                session, tenant_id, empresa_id, candidato
            )
            if criou:
                criados = 1
            else:
                existentes = 1

        await session.commit()
        log.info(
            "contabil.auto.folha",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            folha_id=str(folha.id),
            criados=criados,
            existentes=existentes,
            pulados=pulados,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=1,
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
        )

    # ── Lançamento de impostos apurados ─────────────────────────────────────

    async def lote_impostos(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> LoteResultado:
        """Lança contabilmente TODOS os impostos apurados de uma competência.

        Decisão de design — fonte do valor: ``parse_apuracao_output`` (via
        ``app.modules.fiscal.snapshots``) usando ``snap.valor_devido``.

        Justificativa: ``parse_apuracao_output`` é o discriminador Pydantic
        canônico do projeto — já implementado, retrocompatível (``extra='ignore'``),
        bem testado e preferível a duplicar lógica de leitura de output_jsonb aqui.
        O ``GuiaPagamento`` seria alternativa Decimal-tipada, mas a guia só existe
        quando o contador emite a DARF; a apuração existe sempre.

        Idempotente: ``UNIQUE(origem_tipo='apuracao', origem_id=apuracao_id)``
        em ``lancamento_contabil`` garante que re-chamadas não duplicam.

        Algoritmo versão: ``ALGORITMO_VERSAO_IMPOSTOS``.
        """
        await self._garantir_empresa(session, empresa_id)
        comp_mes1 = date(competencia.year, competencia.month, 1)
        contas = await self.resolver_contas_impostos(session, empresa_id, comp_mes1)

        proximo = _proximo_mes(comp_mes1)
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia >= comp_mes1)
            .where(ApuracaoFiscal.competencia < proximo)
        )
        apuracoes = (await session.execute(stmt)).scalars().all()

        criados = 0
        existentes = 0
        pulados = 0
        for ap in apuracoes:
            valor = _valor_apuracao(ap.tipo, ap.output_jsonb, ap.input_jsonb)
            if valor is None:
                pulados += 1
                continue
            view = ApuracaoFatoView(
                id=ap.id,
                competencia=ap.competencia,
                tipo=ap.tipo,
                valor=valor,
            )
            candidato = gerar_partidas_de_apuracao(view, contas)
            if candidato is None:
                pulados += 1
                continue
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
            "contabil.auto.impostos",
            empresa_id=str(empresa_id),
            competencia=comp_mes1.isoformat(),
            avaliados=len(apuracoes),
            criados=criados,
            existentes=existentes,
            pulados=pulados,
        )
        return LoteResultado(
            competencia=comp_mes1,
            fatos_avaliados=len(apuracoes),
            lancamentos_criados=criados,
            lancamentos_existentes=existentes,
            fatos_pulados=pulados,
            algoritmo_versao=ALGORITMO_VERSAO_IMPOSTOS,
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


def _valor_apuracao(
    tipo: str,
    output_jsonb: object,
    input_jsonb: object,
) -> Decimal | None:
    """Extrai o valor a recolher de uma ``ApuracaoFiscal``.

    Estratégia: usa ``parse_apuracao_output`` (discriminador Pydantic canônico)
    via ``snap.valor_devido`` para todos os tipos. Exceção documentada:

    * DAS: o ``output_jsonb`` usa chave ``"valor_das"`` (legado Sprint 2,
      ``fiscal/service.py:160``), enquanto ``DasSnapshot.valor`` espera chave
      ``"valor"`` — divergência de nomes herdada. Lemos diretamente
      ``output_jsonb["valor_das"]`` para DAS, evitando zero silencioso.
    * ISS legado: output sem chave ``"iss"`` → ``parse_apuracao_output`` já
      faz fallback para ``input_jsonb.valor`` (``snapshots.py:270``).

    Retorna ``None`` para declarações (dctf, efd_contrib) ou valor <= 0.
    """
    if tipo in ("dctf", "efd_contrib"):
        return None

    out: dict[str, object] = output_jsonb if isinstance(output_jsonb, dict) else {}
    inp: dict[str, object] | None = input_jsonb if isinstance(input_jsonb, dict) else None

    # DAS: chave histórica é "valor_das", não "valor" (ver docstring).
    if tipo == "das":
        raw = out.get("valor_das", "0")
        valor = Decimal(str(raw))
    else:
        snap = parse_apuracao_output(tipo, out, input_jsonb=inp)
        valor = snap.valor_devido

    if valor <= Decimal("0"):
        return None
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
