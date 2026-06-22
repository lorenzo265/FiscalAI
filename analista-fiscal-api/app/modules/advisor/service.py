"""AdvisorService — orquestra anomaly detection + sugestões + digest semanal.

Sprint 15:
  * PR1 — anomaly detection (Camada 1 pura).
  * PR2 — sugestões de otimização (Camada 1 pura).
  * PR3 — weekly digest (Camada 1 obrigatória + Camada 3 opt-in via LLM).

Princípios aplicados:

  * §8.1/8.7 — multi-tenant via RLS; sessão sempre vem do ``SessionDep``.
  * §8.4 — algoritmos puros versionados + golden tests.
  * §8.5 — citação obrigatória nos digests (FonteCitavel persistida em JSONB).
  * §8.6 — re-check determinístico via ``validar_resposta`` quando LLM redige.
  * §8.8 — LLM nunca grava fatos; apenas redige texto a partir do snapshot.
  * §8.9 — idempotência: anomalia via UNIQUE parcial; digest via supersedes.
  * §8.10 — log estruturado + ``algoritmo_versao``/``custo_usd`` persistidos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.advisor.calcula_anomalias import (
    TipoTributoAnomalia,
    detectar_anomalia,
)
from app.modules.advisor.gera_digest_semanal import (
    SugestaoResumo,
    gerar_digest_estruturado,
)
from app.modules.advisor.redigir_texto import (
    redigir_template,
    redigir_via_llm,
)
from app.modules.advisor.repo import (
    AnomaliaFiscalRepo,
    ApuracaoSerieRepo,
    DigestRepo,
    SugestoesRepo,
)
from app.modules.advisor.simula_fator_r import (
    SimulacaoFatorR,
    simular_fator_r,
)
from app.modules.advisor.sugestoes_otimizacao import (
    InsumosSugestoes,
    SugestaoCalculada,
    calcular_sugestoes,
)
from app.modules.empresa.repo import EmpresaRepo
from app.modules.fiscal.repo import TabelaSimplesRepo
from app.shared.db.models import AnomaliaFiscal, DigestSemanal
from app.shared.exceptions import (
    AnomaliaJaDispensada,
    AnomaliaNaoEncontrada,
    DigestJaEnviado,
    DigestJaGeradoNaSemana,
    EmpresaNaoEncontrada,
    EmpresaSemWhatsapp,
    EnvioWhatsappFalhou,
    SemDadosParaSugestao,
)
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender
from app.shared.llm.client import LLMClient
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True, slots=True)
class ResultadoReDeteccao:
    """Sumário da re-detecção para 1 empresa."""

    empresa_id: UUID
    competencia_alvo: date
    tipos_analisados: int
    anomalias_registradas: int  # inserções novas + supersedes (qualquer linha nova)


class AdvisorService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self._empresa_repo = EmpresaRepo(session)
        self._serie_repo = ApuracaoSerieRepo(session)
        self._anomalia_repo = AnomaliaFiscalRepo(session)

    # ── 1) Re-detecção de anomalias para uma empresa ────────────────────

    async def redetectar_empresa(
        self,
        empresa_id: UUID,
        *,
        competencia: date | None = None,
    ) -> ResultadoReDeteccao:
        """Roda detecção para todos os tipos monitorados de uma empresa.

        Args:
            empresa_id: empresa-alvo (RLS-protegida).
            competencia: data dentro do mês-alvo. Default: mês atual no fuso BR.

        Returns:
            ``ResultadoReDeteccao`` com contagem de criadas/atualizadas.

        Raises:
            EmpresaNaoEncontrada: empresa não existe / outro tenant.
        """
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if competencia is None:
            competencia = datetime.now(_TZ_BR).date()

        registradas = 0
        analisados = 0
        for tipo in TipoTributoAnomalia:
            analisados += 1
            serie = await self._serie_repo.serie_por_tipo(
                empresa_id, tipo, ate=competencia
            )
            if not serie:
                continue
            try:
                deteccao = detectar_anomalia(tipo, serie)
            except ValueError:
                log.exception(
                    "advisor.anomalia.input_invalido",
                    empresa_id=str(empresa_id),
                    tipo=tipo.value,
                )
                continue
            if deteccao is None:
                continue
            _, criou = await self._anomalia_repo.registrar_ou_atualizar(
                tenant_id=empresa.tenant_id,
                empresa_id=empresa_id,
                deteccao=deteccao,
            )
            if criou:
                registradas += 1
                log.info(
                    "advisor.anomalia.registrada",
                    empresa_id=str(empresa_id),
                    tipo=tipo.value,
                    competencia=deteccao.competencia.isoformat(),
                    severidade=deteccao.severidade.value,
                    z_score=str(deteccao.z_score),
                )

        return ResultadoReDeteccao(
            empresa_id=empresa_id,
            competencia_alvo=competencia,
            tipos_analisados=analisados,
            anomalias_registradas=registradas,
        )

    # ── 2) Listagem de anomalias abertas (endpoint GET) ─────────────────

    async def listar_abertas(
        self, empresa_id: UUID, *, limit: int = 100
    ) -> list[AnomaliaFiscal]:
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        return await self._anomalia_repo.listar_abertas(empresa_id, limit=limit)

    # ── 3) Dispensa de anomalia ─────────────────────────────────────────

    async def dispensar(
        self,
        empresa_id: UUID,
        anomalia_id: UUID,
        *,
        dispensada_por: UUID,
        motivo: str,
    ) -> AnomaliaFiscal:
        """Marca anomalia como dispensada. Idempotência: 2ª dispensa → 409."""
        anomalia = await self._anomalia_repo.por_id(anomalia_id)
        if anomalia is None or anomalia.empresa_id != empresa_id:
            raise AnomaliaNaoEncontrada(
                f"Anomalia {anomalia_id} não encontrada"
            )
        if anomalia.superseded_by is not None:
            raise AnomaliaNaoEncontrada(
                f"Anomalia {anomalia_id} foi superada por nova versão"
            )
        if anomalia.dispensada_em is not None:
            raise AnomaliaJaDispensada(
                f"Anomalia {anomalia_id} já dispensada em "
                f"{anomalia.dispensada_em.isoformat()}"
            )
        agora = datetime.now(_TZ_BR)
        dispensada = await self._anomalia_repo.dispensar(
            anomalia, dispensada_por=dispensada_por, motivo=motivo, em=agora
        )
        log.info(
            "advisor.anomalia.dispensada",
            empresa_id=str(empresa_id),
            anomalia_id=str(anomalia_id),
            dispensada_por=str(dispensada_por),
        )
        return dispensada

    # ── 4) Sugestões de otimização (Sprint 15 PR2) ──────────────────────

    async def listar_sugestoes(
        self,
        empresa_id: UUID,
        *,
        competencia: date | None = None,
    ) -> list[SugestaoCalculada]:
        """Carrega snapshots da empresa e devolve as sugestões aplicáveis.

        Caminho 100% determinístico (camada 1): folha_12m + receita_12m +
        apurações pendentes → orquestrador puro. LLM não entra aqui.

        Raises:
            EmpresaNaoEncontrada: empresa não existe / outro tenant.
        """
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if competencia is None:
            competencia = datetime.now(_TZ_BR).date()

        sug_repo = SugestoesRepo(self._s)
        apuracoes_pendentes = await sug_repo.apuracoes_das_pendentes(
            empresa_id, ate=competencia
        )

        simulacao = await self._calcular_simulacao_fator_r(
            empresa, competencia=competencia, sug_repo=sug_repo
        )

        insumos = InsumosSugestoes(
            simulacao_fator_r=simulacao,
            apuracoes_pendentes=apuracoes_pendentes,
            competencia_referencia=competencia,
        )
        sugestoes = calcular_sugestoes(insumos)
        log.info(
            "advisor.sugestoes.geradas",
            empresa_id=str(empresa_id),
            competencia=competencia.isoformat(),
            total=len(sugestoes),
            tem_fator_r=simulacao is not None,
        )
        return sugestoes

    async def _calcular_simulacao_fator_r(
        self,
        empresa: object,
        *,
        competencia: date,
        sug_repo: SugestoesRepo,
    ) -> SimulacaoFatorR | None:
        """Simula Fator R quando aplicável; senão devolve None.

        Aplica-se a Simples Nacional com anexo declarado III ou V. Para os
        demais regimes/anexos, sugestão Fator R não cabe e devolvemos None
        sem erro (o orquestrador trata None como "sem sugestão").
        """
        regime = empresa.regime_tributario  # type: ignore[attr-defined]
        anexo = empresa.anexo_simples  # type: ignore[attr-defined]
        if regime != "simples_nacional" or anexo not in ("III", "V"):
            return None

        empresa_id = empresa.id  # type: ignore[attr-defined]
        folha = await sug_repo.folha_12m(empresa_id, ate=competencia)
        receita = await sug_repo.receita_12m(empresa_id, ate=competencia)
        if receita <= 0:
            return None

        tabela_repo = TabelaSimplesRepo(self._s)
        faixas_iii = await tabela_repo.faixas_vigentes("III", competencia)
        faixas_v = await tabela_repo.faixas_vigentes("V", competencia)
        if not faixas_iii or not faixas_v:
            return None

        from app.modules.fiscal.calcula_das import FaixaDAS

        def _to_faixa(row: object) -> FaixaDAS:
            return FaixaDAS(
                faixa=row.faixa,  # type: ignore[attr-defined]
                rbt12_ate=row.rbt12_ate,  # type: ignore[attr-defined]
                aliquota_nominal=row.aliquota_nominal,  # type: ignore[attr-defined]
                parcela_deduzir=row.parcela_deduzir,  # type: ignore[attr-defined]
            )

        try:
            return simular_fator_r(
                folha_12m=folha,
                receita_12m=receita,
                competencia=competencia,
                faixas_anexo_iii=[_to_faixa(f) for f in faixas_iii],
                faixas_anexo_v=[_to_faixa(f) for f in faixas_v],
                uf=empresa.uf,  # type: ignore[attr-defined]
            )
        except SemDadosParaSugestao:
            return None

    # ── 5) Weekly digest (Sprint 15 PR3) ────────────────────────────────

    async def gerar_digest_semanal(
        self,
        empresa_id: UUID,
        *,
        competencia: date | None = None,
        forcar: bool = False,
        llm_client: LLMClient | None = None,
        usar_llm: bool = False,
    ) -> DigestSemanal:
        """Gera o digest da semana ISO de ``competencia`` e persiste.

        Args:
            empresa_id: empresa-alvo.
            competencia: data dentro da semana-alvo. Default: hoje BR.
            forcar: se True, gera nova versão mesmo havendo digest ativo
                (a anterior recebe ``superseded_by`` apontando à nova).
                Default False → 409 ``DigestJaGeradoNaSemana``.
            llm_client: instância opcional do ``LLMClient``. Quando
                ``usar_llm=True``, é obrigatório.
            usar_llm: opt-in para Camada 3 (Gemini Flash redige o texto).
                Default False — usa template determinístico.

        Returns:
            ``DigestSemanal`` persistido (status='preparado').

        Raises:
            EmpresaNaoEncontrada: empresa não existe / outro tenant.
            DigestJaGeradoNaSemana: já há ativo e ``forcar=False``.
        """
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if competencia is None:
            competencia = datetime.now(_TZ_BR).date()

        iso_year, iso_week, _ = competencia.isocalendar()
        semana_iso = f"{iso_year:04d}-W{iso_week:02d}"

        digest_repo = DigestRepo(self._s)
        existente = await digest_repo.ativo_por_semana(empresa_id, semana_iso)
        if existente is not None and not forcar:
            raise DigestJaGeradoNaSemana(
                f"Digest para {semana_iso} já existe; use forcar=true para "
                f"regerar."
            )

        # Carregar snapshots — semana ISO segunda→domingo da competência
        periodo_inicio = competencia - timedelta(days=competencia.weekday())
        periodo_fim = periodo_inicio + timedelta(days=6)

        apuracoes = await digest_repo.apuracoes_da_semana(
            empresa_id, inicio=periodo_inicio, fim=periodo_fim
        )
        anomalias = await digest_repo.anomalias_abertas_para_digest(empresa_id)
        vencimentos = await digest_repo.agenda_proximos_vencimentos(
            empresa_id, a_partir_de=competencia
        )
        sugestoes_calc = await self.listar_sugestoes(
            empresa_id, competencia=competencia
        )
        sugestoes_resumo = [
            SugestaoResumo(
                codigo=s.codigo,
                titulo=s.titulo,
                descricao=s.descricao,
                severidade=s.severidade,
                economia_anual_estimada=s.economia_anual_estimada,
            )
            for s in sugestoes_calc
        ]

        nome = empresa.nome_fantasia or empresa.razao_social
        digest_estruturado = gerar_digest_estruturado(
            empresa_nome=nome,
            apuracoes_semana=apuracoes,
            anomalias_abertas=anomalias,
            agenda_proximos=vencimentos,
            sugestoes=sugestoes_resumo,
            referencia=competencia,
        )

        # Redação — template por default; LLM se habilitado
        if usar_llm and llm_client is not None:
            redacao = await redigir_via_llm(
                digest_estruturado,
                llm_client=llm_client,
                empresa_id=str(empresa_id),
            )
        else:
            redacao = redigir_template(digest_estruturado)

        # Persistência
        novo_id = uuid4()
        novo = DigestSemanal(
            id=novo_id,
            tenant_id=empresa.tenant_id,
            empresa_id=empresa_id,
            semana_iso=semana_iso,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            conteudo_estruturado=_serializar_estruturado(digest_estruturado),
            texto_redigido=redacao.texto,
            fonte_redacao=redacao.fonte.value,
            citacoes=list(redacao.citacoes_fato_ids),
            status="preparado",
            llm_provider=redacao.llm_provider,
            custo_usd=redacao.custo_usd,
            tokens_input=redacao.tokens_input,
            tokens_output=redacao.tokens_output,
            tokens_cached=redacao.tokens_cached,
            idempotency_key=uuid4(),
            algoritmo_versao=digest_estruturado.algoritmo_versao,
        )
        if existente is not None:
            await digest_repo.marcar_superseded(existente, novo_id)
        await digest_repo.adicionar(novo)
        log.info(
            "advisor.digest.gerado",
            empresa_id=str(empresa_id),
            semana_iso=semana_iso,
            fonte_redacao=redacao.fonte.value,
            apuracoes_n=len(digest_estruturado.apuracoes),
            anomalias_n=len(digest_estruturado.anomalias),
            sugestoes_n=len(digest_estruturado.sugestoes),
            custo_usd=str(redacao.custo_usd) if redacao.custo_usd else None,
        )
        return novo

    async def listar_digests(
        self, empresa_id: UUID, *, limit: int = 50
    ) -> list[DigestSemanal]:
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        return await DigestRepo(self._s).listar(empresa_id, limit=limit)

    async def obter_digest(
        self, empresa_id: UUID, digest_id: UUID
    ) -> DigestSemanal:
        digest = await DigestRepo(self._s).por_id(digest_id)
        if digest is None or digest.empresa_id != empresa_id:
            raise EmpresaNaoEncontrada(  # genérico — não vazamos existência cross-tenant
                f"Digest {digest_id} não encontrado"
            )
        return digest

    # ── 6) Envio do digest via Meta WhatsApp (Sprint 15.5) ──────────────

    async def enviar_digest_via_whatsapp(
        self,
        empresa_id: UUID,
        digest_id: UUID,
        *,
        sender: MetaWhatsAppSender,
        settings: Settings,
    ) -> DigestSemanal:
        """Envia o digest via Meta WhatsApp utility template.

        Idempotência (§8.9): se ``status='enviado'`` → 409 ``DigestJaEnviado``.
        Status ``preparado`` ou ``falhou`` (após 5 tentativas) podem ser
        re-tentados — o worker semanal aproveita isso para tentar novamente
        em semanas seguintes se a Meta voltar.

        Args:
            empresa_id: empresa dona do digest (defesa em profundidade do RLS).
            digest_id: digest a enviar.
            sender: instância do ``MetaWhatsAppSender`` (DI no router/worker).
            settings: ``Settings`` para ler flag + template_name + lang_code.

        Returns:
            ``DigestSemanal`` atualizado (status='enviado' no caso feliz).

        Raises:
            EmpresaNaoEncontrada: digest não existe ou de outra empresa.
            EmpresaSemWhatsapp: empresa sem ``whatsapp_phone``.
            DigestJaEnviado: já está com ``status='enviado'``.
            EnvioWhatsappFalhou: flag desativada OR Meta rejeitou após retries.
        """
        if not settings.WHATSAPP_DIGEST_TEMPLATE_ATIVO:
            raise EnvioWhatsappFalhou(
                "WHATSAPP_DIGEST_TEMPLATE_ATIVO=False — envio bloqueado por "
                "configuração (template Meta ainda não aprovado)."
            )

        digest_repo = DigestRepo(self._s)
        digest = await digest_repo.por_id(digest_id)
        if digest is None or digest.empresa_id != empresa_id:
            raise EmpresaNaoEncontrada(f"Digest {digest_id} não encontrado")
        if digest.superseded_by is not None:
            raise EmpresaNaoEncontrada(
                f"Digest {digest_id} foi superado por nova versão"
            )
        if digest.status == "enviado":
            raise DigestJaEnviado(
                f"Digest {digest_id} já enviado em "
                f"{digest.enviado_via_whatsapp_em}"
            )

        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if not empresa.whatsapp_phone:
            raise EmpresaSemWhatsapp(
                f"Empresa {empresa_id} sem whatsapp_phone — cadastre antes de enviar."
            )

        # Extrai apelido curto do snapshot (gerado pelo gera_digest_semanal).
        conteudo = digest.conteudo_estruturado
        apelido = (
            conteudo["empresa_apelido_curto"]
            if isinstance(conteudo, dict) and "empresa_apelido_curto" in conteudo
            else (empresa.nome_fantasia or empresa.razao_social)
        )
        corpo = digest.texto_redigido[:1024]  # limite Meta UTILITY

        try:
            await sender.enviar_template(
                empresa.whatsapp_phone,
                template_name=settings.WHATSAPP_DIGEST_TEMPLATE_NAME,
                language_code=settings.WHATSAPP_DIGEST_LANG_CODE,
                body_parameters=[str(apelido), corpo],
            )
        except EnvioWhatsappFalhou as exc:
            await digest_repo.registrar_falha_envio(digest, erro=str(exc))
            log.warning(
                "advisor.digest.envio_falhou",
                empresa_id=str(empresa_id),
                digest_id=str(digest_id),
                tentativas=digest.tentativas_envio,
                status=digest.status,
            )
            raise

        agora = datetime.now(_TZ_BR)
        await digest_repo.marcar_enviado(
            digest,
            em=agora,
            template_name=settings.WHATSAPP_DIGEST_TEMPLATE_NAME,
        )
        log.info(
            "advisor.digest.enviado",
            empresa_id=str(empresa_id),
            digest_id=str(digest_id),
            template_name=settings.WHATSAPP_DIGEST_TEMPLATE_NAME,
        )
        return digest


def _serializar_estruturado(digest: object) -> JsonObject:
    """Serializa ``DigestEstruturado`` para JSONB — todos os Decimal viram str."""
    # ``digest`` é DigestEstruturado; tipado como object para evitar import
    # circular nos type checkers de runtime — atributos são acessados via getattr.
    apuracoes = digest.apuracoes
    anomalias = digest.anomalias
    vencimentos = digest.proximos_vencimentos
    sugestoes = digest.sugestoes
    return {
        "empresa_nome": digest.empresa_nome,
        "empresa_apelido_curto": digest.empresa_apelido_curto,
        "semana_iso": digest.semana_iso,
        "periodo_inicio": digest.periodo_inicio.isoformat(),
        "periodo_fim": digest.periodo_fim.isoformat(),
        "apuracoes": [
            {
                "apuracao_id": a.apuracao_id,
                "tipo": a.tipo,
                "competencia": a.competencia.isoformat(),
                "valor": str(a.valor),
            }
            for a in apuracoes
        ],
        "anomalias": [
            {
                "anomalia_id": an.anomalia_id,
                "tipo": an.tipo,
                "competencia": an.competencia.isoformat(),
                "severidade": an.severidade,
                "mensagem": an.mensagem,
                "valor_observado": str(an.valor_observado),
                "valor_esperado": str(an.valor_esperado),
            }
            for an in anomalias
        ],
        "proximos_vencimentos": [
            {
                "agenda_item_id": v.agenda_item_id,
                "titulo": v.titulo,
                "data_vencimento": v.data_vencimento.isoformat(),
                "tipo_obrigacao": v.tipo_obrigacao,
            }
            for v in vencimentos
        ],
        "sugestoes": [
            {
                "codigo": s.codigo,
                "titulo": s.titulo,
                "descricao": s.descricao,
                "severidade": s.severidade,
                "economia_anual_estimada": (
                    str(s.economia_anual_estimada)
                    if s.economia_anual_estimada is not None
                    else None
                ),
            }
            for s in sugestoes
        ],
        "fontes": [
            {"id": f.id, "tipo": f.tipo, "payload": f.payload, "data": f.data}
            for f in digest.fontes
        ],
        "algoritmo_versao": digest.algoritmo_versao,
    }
