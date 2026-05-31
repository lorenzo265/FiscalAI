"""Repositórios do AI Advisor (Sprint 15).

  * ``ApuracaoSerieRepo`` — leitura de séries temporais de ``apuracao_fiscal``.
  * ``AnomaliaFiscalRepo`` — CRUD append-only de ``anomalia_fiscal``.
  * ``SugestoesRepo`` (Sprint 15 PR2) — folha_12m + receita_12m + DAS pendentes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.advisor.calcula_anomalias import (
    AnomaliaDetectada,
    PontoApuracao,
    TipoTributoAnomalia,
)
from app.modules.advisor.sugestoes_otimizacao import ApuracaoPendente
from app.modules.fiscal.snapshots import parse_apuracao_output
from app.modules.advisor.gera_digest_semanal import (
    ApuracaoResumo,
    AnomaliaResumo,
    VencimentoResumo,
)
from app.shared.db.models import (
    AgendaItem,
    AnomaliaFiscal,
    ApuracaoFiscal,
    DigestSemanal,
    DocumentoFiscal,
    FolhaMensal,
    Holerite,
    ProlaboreMensal,
)


_TIPOS_APURACAO_ANOMALIA: tuple[str, ...] = tuple(t.value for t in TipoTributoAnomalia)


class ApuracaoSerieRepo:
    """Lê apurações fiscais como série temporal por (empresa, tipo)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def serie_por_tipo(
        self,
        empresa_id: UUID,
        tipo: TipoTributoAnomalia,
        *,
        ate: date,
        meses: int = 13,
    ) -> list[PontoApuracao]:
        """Retorna até ``meses`` apurações do tipo, ordenadas por competência ASC.

        ``ate`` define o último ponto-alvo (competência mais recente). Por
        default lê 13 meses para o algoritmo z-score ter ≥ 6 histórico + 1
        alvo, com folga para sazonalidade anual.

        Inclui apenas status ∈ ('calculado', 'transmitido', 'pago') — apurações
        com status diferente (raras) ficam fora da baseline.
        """
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.tipo == tipo.value)
            .where(ApuracaoFiscal.competencia <= ate)
            .where(ApuracaoFiscal.status.in_(("calculado", "transmitido", "pago")))
            .order_by(ApuracaoFiscal.competencia.desc())
            .limit(meses)
        )
        linhas = list((await self._s.execute(stmt)).scalars().all())
        linhas.reverse()  # ASC para algoritmo

        pontos: list[PontoApuracao] = []
        for ap in linhas:
            snap = parse_apuracao_output(
                ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb
            )
            pontos.append(
                PontoApuracao(competencia=ap.competencia, valor=snap.valor_devido)
            )
        return pontos

    @staticmethod
    def tipos_monitorados() -> tuple[str, ...]:
        """Tipos de apuração rastreados (espelha o CHECK do DB)."""
        return _TIPOS_APURACAO_ANOMALIA


class AnomaliaFiscalRepo:
    """CRUD de ``anomalia_fiscal`` — append-only com supersedes (§8.2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def ativa_por_chave(
        self,
        empresa_id: UUID,
        tipo: TipoTributoAnomalia,
        competencia: date,
    ) -> AnomaliaFiscal | None:
        """Retorna a versão ativa (``superseded_by IS NULL``) para a chave."""
        stmt = (
            select(AnomaliaFiscal)
            .where(AnomaliaFiscal.empresa_id == empresa_id)
            .where(AnomaliaFiscal.tipo == tipo.value)
            .where(AnomaliaFiscal.competencia == competencia)
            .where(AnomaliaFiscal.superseded_by.is_(None))
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_id(self, anomalia_id: UUID) -> AnomaliaFiscal | None:
        stmt = select(AnomaliaFiscal).where(AnomaliaFiscal.id == anomalia_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_abertas(
        self, empresa_id: UUID, *, limit: int = 100
    ) -> list[AnomaliaFiscal]:
        """Anomalias ativas (não-superadas) e não-dispensadas, mais recentes primeiro."""
        stmt = (
            select(AnomaliaFiscal)
            .where(AnomaliaFiscal.empresa_id == empresa_id)
            .where(AnomaliaFiscal.superseded_by.is_(None))
            .where(AnomaliaFiscal.dispensada_em.is_(None))
            .order_by(AnomaliaFiscal.detectado_em.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def registrar_ou_atualizar(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        deteccao: AnomaliaDetectada,
    ) -> tuple[AnomaliaFiscal, bool]:
        """Insere nova anomalia ou supera a anterior da mesma chave.

        Idempotência (§8.9): se já existe linha ativa para
        ``(empresa, tipo, competencia)`` com **mesmo** ``valor_observado`` e
        ``severidade``, devolve a existente sem tocar no DB (retorno
        ``criou=False``).

        Caso contrário, cria nova linha e — se havia anterior — faz
        ``UPDATE`` marcando a anterior com ``superseded_by = nova.id``.
        """
        existente = await self.ativa_por_chave(
            empresa_id, deteccao.tipo, deteccao.competencia
        )
        if existente is not None and _mesma_deteccao(existente, deteccao):
            return existente, False

        nova_id = uuid4()
        nova = AnomaliaFiscal(
            id=nova_id,
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=deteccao.tipo.value,
            competencia=deteccao.competencia,
            severidade=deteccao.severidade.value,
            valor_observado=deteccao.valor_observado,
            valor_esperado=deteccao.valor_esperado,
            z_score=deteccao.z_score,
            delta_percentual=deteccao.delta_percentual,
            metodo=deteccao.metodo.value,
            amostra_n=deteccao.amostra_n,
            mensagem=deteccao.mensagem,
            algoritmo_versao=deteccao.algoritmo_versao,
        )
        if existente is not None:
            # Supera a anterior ANTES de inserir a nova — UNIQUE parcial
            # exige no máximo 1 linha ativa por chave a qualquer momento.
            await self._s.execute(
                update(AnomaliaFiscal)
                .where(AnomaliaFiscal.id == existente.id)
                .values(superseded_by=nova_id)
            )
        self._s.add(nova)
        await self._s.flush()
        return nova, True

    async def dispensar(
        self,
        anomalia: AnomaliaFiscal,
        *,
        dispensada_por: UUID,
        motivo: str,
        em: datetime,
    ) -> AnomaliaFiscal:
        """Marca a anomalia como dispensada (UPDATE in-place — não viola §8.2;
        dispensa é metadado de status do alerta, não alteração de fato).
        """
        anomalia.dispensada_em = em
        anomalia.dispensada_por = dispensada_por
        anomalia.motivo_dispensa = motivo
        await self._s.flush()
        return anomalia


def _mesma_deteccao(linha: AnomaliaFiscal, det: AnomaliaDetectada) -> bool:
    """True quando o snapshot persistido bate com a detecção recém-calculada."""
    return (
        linha.valor_observado == det.valor_observado
        and linha.severidade == det.severidade.value
        and linha.metodo == det.metodo.value
        and Decimal(str(linha.z_score)) == det.z_score
    )


# ── Sprint 15 PR2 — Sugestões de otimização ────────────────────────────────


_DELTA_UM_DIA = timedelta(days=1)


def _periodo_12m_ate(competencia: date) -> tuple[date, date]:
    """Retorna (inicio, fim) cobrindo os 12m anteriores a ``competencia``.

    ``fim`` = último dia do mês anterior à competência.
    ``inicio`` = primeiro dia do mês 11 meses antes do fim (12 meses ao todo).
    """
    fim_mes = competencia.replace(day=1) - _DELTA_UM_DIA
    ano_inicio = fim_mes.year - 1
    mes_inicio = fim_mes.month + 1
    if mes_inicio > 12:
        mes_inicio -= 12
        ano_inicio += 1
    inicio = date(ano_inicio, mes_inicio, 1)
    return inicio, fim_mes


def _vencimento_das(competencia: date) -> date:
    """Vencimento do DAS — dia 20 do mês seguinte à competência (LC 123 art. 21).

    Se 20 cai em fim de semana/feriado, o pagamento prorroga; este algoritmo
    usa a data nominal — sugestão é aproximação, não cobrança exata.
    """
    if competencia.month == 12:
        return date(competencia.year + 1, 1, 20)
    return date(competencia.year, competencia.month + 1, 20)


class SugestoesRepo:
    """Repo do PR2 — carrega folha_12m + receita_12m + DAS pendentes."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def folha_12m(self, empresa_id: UUID, ate: date) -> Decimal:
        """Soma salário bruto + pró-labore dos últimos 12 meses.

        ``Holerite`` não carrega ``empresa_id`` direto — junta via
        ``FolhaMensal.empresa_id``. ``ProlaboreMensal`` tem ``empresa_id``
        próprio.
        """
        inicio, fim = _periodo_12m_ate(ate)
        stmt_hol = (
            select(func.coalesce(func.sum(Holerite.salario_bruto), 0))
            .join(FolhaMensal, FolhaMensal.id == Holerite.folha_mensal_id)
            .where(FolhaMensal.empresa_id == empresa_id)
            .where(Holerite.competencia >= inicio)
            .where(Holerite.competencia <= fim)
        )
        salarios = Decimal(
            (await self._s.execute(stmt_hol)).scalar_one()
        )

        stmt_pro = (
            select(func.coalesce(func.sum(ProlaboreMensal.valor_bruto), 0))
            .where(ProlaboreMensal.empresa_id == empresa_id)
            .where(ProlaboreMensal.competencia >= inicio)
            .where(ProlaboreMensal.competencia <= fim)
        )
        prolabore = Decimal(
            (await self._s.execute(stmt_pro)).scalar_one()
        )
        return salarios + prolabore

    async def receita_12m(self, empresa_id: UUID, ate: date) -> Decimal:
        """Soma ``valor_total`` de saídas autorizadas nos últimos 12 meses."""
        inicio, fim = _periodo_12m_ate(ate)
        stmt = (
            select(func.coalesce(func.sum(DocumentoFiscal.valor_total), 0))
            .where(DocumentoFiscal.empresa_id == empresa_id)
            .where(DocumentoFiscal.direcao == "saida")
            .where(DocumentoFiscal.status == "autorizada")
            .where(DocumentoFiscal.superseded_by.is_(None))
            .where(DocumentoFiscal.emitida_em >= inicio)
            .where(DocumentoFiscal.emitida_em <= fim)
        )
        return Decimal((await self._s.execute(stmt)).scalar_one())

    async def apuracoes_das_pendentes(
        self, empresa_id: UUID, *, ate: date
    ) -> list[ApuracaoPendente]:
        """Apurações DAS com ``pago_em IS NULL`` cuja competência já passou.

        Devolve dataclasses puros (sem ORM) para o orquestrador determinístico.
        """
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.tipo == "das")
            .where(ApuracaoFiscal.competencia <= ate)
            .where(ApuracaoFiscal.pago_em.is_(None))
            .order_by(ApuracaoFiscal.competencia)
        )
        linhas = list((await self._s.execute(stmt)).scalars().all())

        pendentes: list[ApuracaoPendente] = []
        for ap in linhas:
            snap = parse_apuracao_output(
                ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb
            )
            pendentes.append(
                ApuracaoPendente(
                    apuracao_id=str(ap.id),
                    tipo=ap.tipo,
                    competencia=ap.competencia,
                    valor=snap.valor_devido,
                    vencimento=_vencimento_das(ap.competencia),
                    status=ap.status,
                )
            )
        return pendentes


# ── Sprint 15 PR3 — Weekly digest ───────────────────────────────────────────


class DigestRepo:
    """CRUD de ``digest_semanal`` — append-only com supersedes (§8.2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, digest_id: UUID) -> DigestSemanal | None:
        stmt = select(DigestSemanal).where(DigestSemanal.id == digest_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def ativo_por_semana(
        self, empresa_id: UUID, semana_iso: str
    ) -> DigestSemanal | None:
        stmt = (
            select(DigestSemanal)
            .where(DigestSemanal.empresa_id == empresa_id)
            .where(DigestSemanal.semana_iso == semana_iso)
            .where(DigestSemanal.superseded_by.is_(None))
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self, empresa_id: UUID, *, limit: int = 50
    ) -> list[DigestSemanal]:
        stmt = (
            select(DigestSemanal)
            .where(DigestSemanal.empresa_id == empresa_id)
            .where(DigestSemanal.superseded_by.is_(None))
            .order_by(DigestSemanal.criado_em.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def adicionar(self, digest: DigestSemanal) -> DigestSemanal:
        self._s.add(digest)
        await self._s.flush()
        return digest

    async def marcar_superseded(
        self, anterior: DigestSemanal, novo_id: UUID
    ) -> None:
        await self._s.execute(
            update(DigestSemanal)
            .where(DigestSemanal.id == anterior.id)
            .values(superseded_by=novo_id)
        )

    # ── Sprint 15.5 — auditoria de envio ──────────────────────────────

    async def marcar_enviado(
        self,
        digest: DigestSemanal,
        *,
        em: datetime,
        template_name: str,
    ) -> None:
        """Transição preparado → enviado (UPDATE in-place — não viola §8.2,
        envio é metadado de transmissão, não fato fiscal).
        """
        await self._s.execute(
            update(DigestSemanal)
            .where(DigestSemanal.id == digest.id)
            .values(
                status="enviado",
                enviado_via_whatsapp_em=em,
                enviado_template_name=template_name,
                ultimo_erro_envio=None,
            )
        )
        digest.status = "enviado"
        digest.enviado_via_whatsapp_em = em
        digest.enviado_template_name = template_name
        digest.ultimo_erro_envio = None

    async def registrar_falha_envio(
        self,
        digest: DigestSemanal,
        *,
        erro: str,
        limite_tentativas: int = 5,
    ) -> None:
        """Incrementa contador de tentativas; promove a 'falhou' no limite."""
        novas_tentativas = digest.tentativas_envio + 1
        novo_status = (
            "falhou" if novas_tentativas >= limite_tentativas else digest.status
        )
        erro_truncado = erro[:500]
        await self._s.execute(
            update(DigestSemanal)
            .where(DigestSemanal.id == digest.id)
            .values(
                tentativas_envio=novas_tentativas,
                ultimo_erro_envio=erro_truncado,
                status=novo_status,
            )
        )
        digest.tentativas_envio = novas_tentativas
        digest.ultimo_erro_envio = erro_truncado
        digest.status = novo_status

    # ── Snapshots para gera_digest_semanal ──────────────────────────────

    async def apuracoes_da_semana(
        self,
        empresa_id: UUID,
        *,
        inicio: date,
        fim: date,
    ) -> list[ApuracaoResumo]:
        """Apurações cuja competência cai dentro da semana ISO."""
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia >= inicio)
            .where(ApuracaoFiscal.competencia <= fim)
            .order_by(ApuracaoFiscal.competencia.desc())
        )
        resumo: list[ApuracaoResumo] = []
        for ap in (await self._s.execute(stmt)).scalars().all():
            snap = parse_apuracao_output(
                ap.tipo, ap.output_jsonb, input_jsonb=ap.input_jsonb
            )
            resumo.append(
                ApuracaoResumo(
                    apuracao_id=str(ap.id),
                    tipo=ap.tipo,
                    competencia=ap.competencia,
                    valor=snap.valor_devido,
                )
            )
        return resumo

    async def anomalias_abertas_para_digest(
        self, empresa_id: UUID, *, limit: int = 10
    ) -> list[AnomaliaResumo]:
        """Anomalias ativas + não-dispensadas — top severidade."""
        stmt = (
            select(AnomaliaFiscal)
            .where(AnomaliaFiscal.empresa_id == empresa_id)
            .where(AnomaliaFiscal.superseded_by.is_(None))
            .where(AnomaliaFiscal.dispensada_em.is_(None))
            .order_by(AnomaliaFiscal.detectado_em.desc())
            .limit(limit)
        )
        return [
            AnomaliaResumo(
                anomalia_id=str(an.id),
                tipo=an.tipo,
                competencia=an.competencia,
                severidade=an.severidade,
                mensagem=an.mensagem,
                valor_observado=an.valor_observado,
                valor_esperado=an.valor_esperado,
            )
            for an in (await self._s.execute(stmt)).scalars().all()
        ]

    async def agenda_proximos_vencimentos(
        self,
        empresa_id: UUID,
        *,
        a_partir_de: date,
        dias: int = 14,
    ) -> list[VencimentoResumo]:
        """Itens da agenda fiscal nos próximos N dias, status pendente."""
        horizonte = a_partir_de + timedelta(days=dias)
        stmt = (
            select(AgendaItem)
            .where(AgendaItem.empresa_id == empresa_id)
            .where(AgendaItem.status == "pendente")
            .where(AgendaItem.data_vencimento >= a_partir_de)
            .where(AgendaItem.data_vencimento <= horizonte)
            .order_by(AgendaItem.data_vencimento)
        )
        return [
            VencimentoResumo(
                agenda_item_id=str(v.id),
                titulo=v.titulo,
                data_vencimento=v.data_vencimento,
                tipo_obrigacao=v.tipo_obrigacao,
            )
            for v in (await self._s.execute(stmt)).scalars().all()
        ]
