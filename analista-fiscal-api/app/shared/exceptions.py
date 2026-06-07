from __future__ import annotations


class DomainError(Exception):
    """Raiz de toda exceção de domínio do Analista Fiscal.

    Erros que herdam de DomainError são mapeados para HTTP 4xx/5xx específicos
    em um único handler em app/main.py. Erros não mapeados viram 500 genérico.
    """

    http_status: int = 400

    def __init__(self, mensagem: str, *, codigo: str | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo or self.__class__.__name__


# ── Validação de entrada (cross-cutting) ─────────────────────────────────────


class CompetenciaInvalida(DomainError):
    """Competência mensal fora do formato AAAA-MM ou com mês/ano inválido."""

    http_status = 422


# ── Auth ─────────────────────────────────────────────────────────────────────


class TokenInvalido(DomainError):
    http_status = 401


class CredenciaisInvalidas(DomainError):
    http_status = 401


class SemPermissao(DomainError):
    http_status = 403


# ── Tenant / Usuário ─────────────────────────────────────────────────────────


class TenantNaoEncontrado(DomainError):
    http_status = 404


class SlugJaCadastrado(DomainError):
    http_status = 409


class EmailJaCadastrado(DomainError):
    http_status = 409


# ── Empresa ──────────────────────────────────────────────────────────────────


class EmpresaNaoEncontrada(DomainError):
    http_status = 404


class CnpjInvalido(DomainError):
    http_status = 422


class OnboardingConflitoComImportacao(DomainError):
    """Bootstrap de empresa colide com lote de importação SPED já concluído.

    Sprint 19 PR4. O onboarding bundle clona o plano de contas referencial RFB,
    mas se a empresa já recebeu importação histórica (Sprint 18 — ECD via SPED),
    o plano dela DEVE vir do SPED original — não do referencial. Conflito de
    códigos contábeis é fatal.

    Resolução operacional: revisar lotes via ``GET /v1/empresas/{eid}/migracao/lotes``,
    decidir entre rollback do lote ou usar plano importado direto. Esta exceção
    bloqueia o bootstrap automático até a decisão ser tomada.
    """

    http_status = 409


class CnpjJaCadastrado(DomainError):
    http_status = 409


class RetificacaoSemOriginal(DomainError):
    """Retificação de obrigação acessória requer transmissão original bem-sucedida.

    PGDAS-D, DEFIS, DASN-SIMEI: a retificadora referencia a declaração anterior;
    sem original transmitida com sucesso, não há o que retificar.
    """

    http_status = 409


class MunicipioIbgeAusente(DomainError):
    """Empresa sem ``codigo_municipio_ibge`` cadastrado — bloqueia emissão NFS-e
    e transmissão PGDAS (ambas APIs exigem código IBGE 7-dígitos).

    Fix: cadastrar via ``PATCH /v1/empresas/{eid}/municipio-ibge`` com 7 dígitos
    do município (consulte tabela IBGE de municípios brasileiros).
    """

    http_status = 422


# ── Ingestão ─────────────────────────────────────────────────────────────────


class XmlInvalido(DomainError):
    http_status = 422


class DocumentoJaIngerido(DomainError):
    http_status = 409


class DocumentoNaoEncontrado(DomainError):
    http_status = 404


# ── Fiscal ───────────────────────────────────────────────────────────────────


class TabelaTributariaAusente(DomainError):
    """Tabela SCD Type 2 não encontrada para a competência solicitada."""

    http_status = 500


class ApuracaoJaExiste(DomainError):
    http_status = 409


class ApuracaoNaoEncontrada(DomainError):
    http_status = 404


class RegimeIncompativel(DomainError):
    """Operação requer regime específico que a empresa não possui."""

    http_status = 422


class FatorRObrigatorio(DomainError):
    """Empresa no Anexo III/V sem folha_12m fornecida."""

    http_status = 422


class EmpresaForaSimplesNacional(DomainError):
    """RBT12 excedeu o teto federal R$4.800.000 — empresa deveria ser desenquadrada do SN.

    LC 123/2006 art. 3º II. Sistema não calcula DAS para empresa fora do SN.
    Ação esperada: o cliente deve mudar de regime tributário (LP/LR) e a empresa
    deve ser sinalizada no frontend (`monitor_cadastral`) como pendente de
    desenquadramento.
    """

    http_status = 422


# ── LLM ──────────────────────────────────────────────────────────────────────


class LLMIndisponivel(DomainError):
    """Provider LLM inacessível (Ollama down, Gemini sem chave, etc.)."""

    http_status = 503


class LLMRespostaInvalida(DomainError):
    """Provider LLM retornou resposta que não pôde ser interpretada."""

    http_status = 502


class LLMCitacaoInvalida(DomainError):
    """Resposta LLM rejeitada pelo validador de citação — nenhum fato verificável encontrado."""

    http_status = 422


# ── Focus NFe / NFS-e ────────────────────────────────────────────────────────


class FocusNfeErro(DomainError):
    """Focus NFe retornou erro HTTP inesperado (4xx/5xx não tratado)."""

    http_status = 502


class FocusNfeTimeout(DomainError):
    """Timeout ou falha de transporte na chamada à Focus NFe."""

    http_status = 504


class NfseJaEmitida(DomainError):
    """Tentativa de emitir NFS-e com ref que já existe e foi autorizada."""

    http_status = 409


class NfseNaoEncontrada(DomainError):
    """Referência Focus NFe não encontrada."""

    http_status = 404


# ── WhatsApp ─────────────────────────────────────────────────────────────────


class WhatsAppAssinaturaInvalida(DomainError):
    """Assinatura HMAC-SHA256 do webhook Meta é inválida."""

    http_status = 401


class WhatsAppErro(DomainError):
    """Falha ao enviar mensagem via Meta WhatsApp Cloud API."""

    http_status = 502


# ── Onboarding / BrasilAPI ───────────────────────────────────────────────────


class CnpjNaoEncontrado(DomainError):
    """CNPJ não encontrado na Receita Federal via BrasilAPI."""

    http_status = 404


class BrasilApiIndisponivel(DomainError):
    """BrasilAPI inacessível após retentativas."""

    http_status = 503


# ── SERPRO Integra Contador (Sprint 6) ───────────────────────────────────────


class SerproErro(DomainError):
    """SERPRO retornou erro HTTP inesperado (4xx/5xx não tratado)."""

    http_status = 502


class SerproTimeout(DomainError):
    """Timeout ou falha de transporte na chamada ao SERPRO."""

    http_status = 504


class SerproOAuthErro(DomainError):
    """Falha ao obter token OAuth2 do SERPRO (credenciais inválidas, etc.)."""

    http_status = 502


class SerproCredencialAusente(DomainError):
    """Empresa ainda não fez opt-in com certificado e-CNPJ para SERPRO."""

    http_status = 412


# ── Compliance / Certidões ───────────────────────────────────────────────────


class CertidaoNaoEncontrada(DomainError):
    http_status = 404


class CertidaoEmissaoFalhou(DomainError):
    """Falha ao emitir certidão (CND/CRF/CNDT) — origem upstream."""

    http_status = 502


# ── Pluggy / Open Finance (Sprint 7) ─────────────────────────────────────────


class PluggyErro(DomainError):
    """Pluggy retornou erro HTTP inesperado (4xx/5xx não tratado).

    O ``status_upstream`` (HTTP do response Pluggy, não o nosso 502) permite
    que o ``SyncService`` decida retentar (5xx / 429) ou abortar (4xx).
    """

    http_status = 502

    def __init__(
        self,
        mensagem: str,
        *,
        codigo: str | None = None,
        status_upstream: int | None = None,
    ) -> None:
        super().__init__(mensagem, codigo=codigo)
        self.status_upstream = status_upstream

    @property
    def retentavel(self) -> bool:
        """True para 5xx ou 429 — instabilidade transitória. 4xx aborta."""
        if self.status_upstream is None:
            return True
        return self.status_upstream >= 500 or self.status_upstream == 429


class PluggyTimeout(DomainError):
    """Timeout ou falha de transporte na chamada à API Pluggy."""

    http_status = 504


class PluggyOAuthErro(DomainError):
    """Falha ao obter API key Pluggy (credenciais inválidas, etc.)."""

    http_status = 502


class ItemNaoEncontrado(DomainError):
    """Pluggy item não encontrado (foi removido ou nunca foi registrado)."""

    http_status = 404


class ItemJaRegistrado(DomainError):
    """Tentativa de registrar pluggy_item_id que já existe (idempotência)."""

    http_status = 409


class WebhookPluggyAssinaturaInvalida(DomainError):
    """Assinatura HMAC do webhook Pluggy não confere com o segredo."""

    http_status = 401


# ── Conciliação (Sprint 7 PR3) ───────────────────────────────────────────────


class MatchNaoEncontrado(DomainError):
    """Conciliação match não encontrado para o (empresa, id) informado."""

    http_status = 404


class MatchJaResolvido(DomainError):
    """Tentativa de confirmar/rejeitar match já em estado terminal."""

    http_status = 409


# ── Imobilizado (Sprint 8 PR1) ───────────────────────────────────────────────


class BemNaoEncontrado(DomainError):
    """Bem imobilizado não localizado para a empresa informada."""

    http_status = 404


class BemJaBaixado(DomainError):
    """Tentativa de baixar bem já baixado, ou data de baixa anterior à aquisição."""

    http_status = 409


# ── Contábil (Sprint 9 PR1) ──────────────────────────────────────────────────


class ContaJaExiste(DomainError):
    """Conta contábil com o mesmo código já está vigente na empresa."""

    http_status = 409


class LancamentoInvalido(DomainError):
    """Partidas não passaram na validação (D≠C, conta sintética, fora vigência)."""

    http_status = 422


class LancamentoNaoEncontrado(DomainError):
    http_status = 404


class LancamentoJaConfirmado(DomainError):
    """Lançamento confirmado/encerrado não pode mudar de estado."""

    http_status = 409


class PlanoContasIncompleto(DomainError):
    """Empresa não tem todas as contas padrão necessárias para o motor automático."""

    http_status = 412


class ContaContabilNaoEncontrada(DomainError):
    """Conta contábil não localizada na empresa informada."""

    http_status = 404


class CompetenciaJaEncerrada(DomainError):
    """Tentativa de encerrar competência que já foi encerrada (idempotência §8.2)."""

    http_status = 409


class LancamentoEmMesEncerrado(DomainError):
    """Tentativa de criar/editar lançamento manual em competência já encerrada.

    Defesa em profundidade além do CHECK em ``status`` no DB — bloqueia no service
    para devolver mensagem clara ao cliente. Fluxo correto: lançamento de ajuste
    retroativo em competência aberta com histórico explícito.
    """

    http_status = 409


class EncerramentoMensalAusente(DomainError):
    """Encerramento anual requer dezembro encerrado primeiro (saldos materializados)."""

    http_status = 409


class ExercicioJaAberto(DomainError):
    """Tentativa de reabrir exercício para um ano que já tem saldos de janeiro materializados.

    Idempotência (§8.9): ``abrir_exercicio(2025)`` chamado 2× retorna o resultado anterior
    sem reescrever. Esta exceção só é levantada quando o cliente força ``forcar=False``
    em chamada explícita.
    """

    http_status = 409


# ── Migração de escritório antigo (Sprint 18) ────────────────────────────────


class LoteImportacaoNaoEncontrado(DomainError):
    """Lote de importação SPED/CSV não localizado para o tenant atual."""

    http_status = 404


class SpedInvalido(DomainError):
    """Arquivo SPED malformado ou com amarrações quebradas.

    O parser ECD/ECF levanta ``EcdInvalido``/``EcfInvalido`` (subclasses de
    ``ValueError``) — o service re-raises como ``SpedInvalido`` para que o
    handler HTTP devolva 422 com a mensagem original.
    """

    http_status = 422


class EmpresaCnpjDivergente(DomainError):
    """CNPJ do registro 0000 do SPED não bate com o ``Empresa.cnpj`` cadastrado.

    Proteção §8.6 (re-check determinístico): escritório antigo entregou
    SPED de outra empresa por engano — rejeitamos antes de qualquer escrita.
    """

    http_status = 422


class PeriodoForaCobertura(DomainError):
    """Período do SPED é anterior ao corte aceito pelo importador.

    Sprint 18 PR2 corta em **2024-01-01** — SPED de exercícios anteriores
    cai aqui (faltam vigências SCD para validar cruzado, e PME jovem
    tipicamente não tem histórico tão antigo).
    """

    http_status = 422


class VigenciaScdAusente(DomainError):
    """Lançamento importado pisa em competência sem vigência SCD coberta.

    Hoje a Sprint 18 PR2 não exige SCD para os lançamentos (não recalculamos
    — só importamos os fatos do escritório antigo). Reservado para PR3
    quando importador EFD-Contribuições/ICMS-IPI cruzar com alíquotas.
    """

    http_status = 422


# ── Pessoal / Folha (Sprint 10 PR1) ──────────────────────────────────────────


class FuncionarioNaoEncontrado(DomainError):
    http_status = 404


class CpfInvalido(DomainError):
    """CPF não tem 11 dígitos ou falha no algoritmo dos dígitos verificadores."""

    http_status = 422


class CpfJaCadastrado(DomainError):
    """Tentativa de cadastrar CPF que já existe para a mesma empresa."""

    http_status = 409


class FuncionarioInativo(DomainError):
    """Tentativa de incluir funcionário inativo/demitido em folha aberta."""

    http_status = 409


class FolhaNaoEncontrada(DomainError):
    http_status = 404


class FolhaJaFechada(DomainError):
    """Tentativa de alterar holerite ou reabrir folha já fechada (§8.2)."""

    http_status = 409


class EventoFolhaJaExiste(DomainError):
    """Evento (13º, férias, rescisão) já registrado para o funcionário."""

    http_status = 409


class ParametrosFolhaInvalidos(DomainError):
    """Parâmetros de cálculo de 13º/férias/rescisão fora dos limites legais."""

    http_status = 422


class FuncionarioJaDemitido(DomainError):
    """Tentativa de rescindir funcionário já demitido."""

    http_status = 409


# ── Pessoal PR3 (sócio + pró-labore + distribuição + eSocial) ────────────────


class SocioNaoEncontrado(DomainError):
    http_status = 404


class CpfSocioJaCadastrado(DomainError):
    """CPF do sócio já cadastrado para a empresa."""

    http_status = 409


class ProlaboreJaRegistrado(DomainError):
    """Pró-labore do (sócio, competência) já registrado."""

    http_status = 409


class DistribuicaoInvalida(DomainError):
    """Parâmetros de distribuição de lucros inválidos (limite < 0, etc.)."""

    http_status = 422


class EventoESocialJaExiste(DomainError):
    """Evento eSocial (tipo, referência) já gerado para a empresa."""

    http_status = 409


# ── Lucro Presumido (Sprint 11 PR1) ──────────────────────────────────────────


class PresuncaoNaoEncontrada(DomainError):
    """Nenhum grupo de presunção LP combina com o CNAE da empresa."""

    http_status = 422


class EmpresaForaDoRegimeLP(DomainError):
    """Apuração LP solicitada para empresa em regime diferente."""

    http_status = 422


class ApuracaoLPJaExiste(DomainError):
    """Apuração LP (empresa, período, tipo) já registrada."""

    http_status = 409


# ── ICMS / EFD-Reinf (Sprint 11 PR2) ─────────────────────────────────────────


class UfNaoSuportada(DomainError):
    """UF inexistente ou sem alíquota ICMS cadastrada na vigência."""

    http_status = 422


class EmpresaSemUf(DomainError):
    """Empresa não tem UF cadastrada — apuração ICMS impossível."""

    http_status = 422


class ApuracaoIcmsJaExiste(DomainError):
    """Apuração ICMS (empresa, competência) já registrada."""

    http_status = 409


class EventoReinfJaExiste(DomainError):
    """Evento EFD-Reinf (empresa, tipo, referência) já gerado."""

    http_status = 409


class RegimeIsentoRetencao(DomainError):
    """Tomador em regime que dispensa retenção PJ→PJ (ex.: SN dispensado)."""

    http_status = 422


# ── DET / Monitor / Parcelamento (Sprint 11 PR3) ─────────────────────────────


class MensagemDetJaExiste(DomainError):
    """Mensagem DET já registrada (idempotência por id_externo_det)."""

    http_status = 409


class ParcelamentoInvalido(DomainError):
    """Parâmetros do parcelamento fora dos limites legais (parcela mínima, nº)."""

    http_status = 422


class ParcelamentoNaoEncontrado(DomainError):
    http_status = 404


class ParcelamentoJaCancelado(DomainError):
    """Tentativa de operar parcelamento em estado terminal (cancelado/rescindido)."""

    http_status = 409


# ── Relatórios (Sprint 12) ───────────────────────────────────────────────────


class RelatorioNaoEncontrado(DomainError):
    http_status = 404


class SemDadosContabeis(DomainError):
    """Empresa não tem movimentação contábil no período solicitado."""

    http_status = 422


# ── Marketplace de contadores parceiros (Sprint 13) ──────────────────────────


class ContadorParceiroNaoEncontrado(DomainError):
    http_status = 404


class CrcInvalido(DomainError):
    """CRC com formato inválido (esperado: dígitos + UF de 2 letras)."""

    http_status = 422


class EmailParceiroJaCadastrado(DomainError):
    """Já existe parceiro com este email (UNIQUE global)."""

    http_status = 409


class CrcJaCadastrado(DomainError):
    """Já existe parceiro com este (crc_numero, crc_uf)."""

    http_status = 409


class EspecialidadeInvalida(DomainError):
    """Especialidade fora do conjunto fechado de especialidades aceitas."""

    http_status = 422


class ConsultaNaoEncontrada(DomainError):
    http_status = 404


class ConsentimentoAusente(DomainError):
    """Cliente não marcou consentimento_compartilhamento=True (§8.7)."""

    http_status = 422


class ConsultaForaDeFluxo(DomainError):
    """Transição de status não permitida pela máquina (ex.: aceitar uma cancelada)."""

    http_status = 409


class ConsultaSlaExpirado(DomainError):
    """SLA de aceitação/resposta vencido — operação rejeitada."""

    http_status = 409


class ConsultaJaAvaliada(DomainError):
    """Cliente já enviou rating para esta consulta."""

    http_status = 409


class ParceiroIndisponivel(DomainError):
    """Parceiro escolhido pelo cliente não está ativo ou não cobre a categoria/UF."""

    http_status = 422


class SemParceirosDisponiveis(DomainError):
    """Nenhum parceiro elegível para a categoria + UF no momento."""

    http_status = 422


class CobrancaInvalida(DomainError):
    """Estado da consulta não permite gerar cobrança (ainda não concluída)."""

    http_status = 422


class CobrancaNaoEncontrada(DomainError):
    http_status = 404


class CredenciaisParceiroInvalidas(DomainError):
    """E-mail/senha do parceiro incorretos ou parceiro inativo."""

    http_status = 401


class WebhookPagamentoAssinaturaInvalida(DomainError):
    """Assinatura HMAC-SHA256 do webhook de pagamento ausente ou inválida.

    Fail-closed: qualquer payload sem assinatura válida é rejeitado antes de
    qualquer processamento (§8.9 — integração externa autenticada).
    """

    http_status = 401


class ParceiroSemSenhaDefinida(DomainError):
    """Parceiro nunca definiu senha — bloqueio fail-closed antes de login."""

    http_status = 401


# ── Reforma Tributária — CBS/IBS informacional (Sprint 14) ───────────────────


class AliquotaCbsIbsAusente(DomainError):
    """Não há vigência de ``aliquota_cbs_ibs`` para a competência solicitada.

    A SCD ``aliquota_cbs_ibs`` deve ter cobertura ininterrupta entre 2026-01-01
    e a data corrente. Esta exceção indica gap de seed (defeito operacional).
    """

    http_status = 422


class BaseCalculoInvalida(DomainError):
    """Base de cálculo CBS/IBS inválida (negativa, NaN ou não-Decimal)."""

    http_status = 422


class PeriodoReformaNaoMapeado(DomainError):
    """Competência fora do cronograma mapeado pela LC 214/2025 (anterior a 2026)."""

    http_status = 422


class SemApuracoesDoPeriodo(DomainError):
    """Empresa não tem apurações fiscais (PIS/Cofins/ICMS/ISS) suficientes nos
    últimos 12 meses para simular impacto da Reforma. Mínimo: pelo menos 1
    apuração das principais. Para empresas recém-cadastradas, simulação
    fica indisponível até a primeira apuração rodar.
    """

    http_status = 422


# ── AI Advisor — anomaly detection (Sprint 15 PR1) ───────────────────────────


class AnomaliaNaoEncontrada(DomainError):
    """Anomalia não existe, foi superada por nova versão, ou pertence a outro tenant."""

    http_status = 404


class AnomaliaJaDispensada(DomainError):
    """Anomalia já dispensada — dispensa é idempotente, mas exposta como 409 ao caller."""

    http_status = 409


class HistoricoInsuficienteParaAnomalia(DomainError):
    """Série temporal curta demais para detectar anomalia (mínimo 3 apurações).

    Empresas recém-cadastradas ou tipos de imposto raros não têm baseline
    suficiente — o worker pula silenciosamente. Esta exceção só aparece em
    chamadas explícitas (endpoint POST de re-detecção, se exposto).
    """

    http_status = 422


# ── AI Advisor — sugestões de otimização (Sprint 15 PR2) ─────────────────────


class SemDadosParaSugestao(DomainError):
    """Empresa sem dados suficientes para calcular sugestão (sem receita 12m,
    sem folha 12m, ou ambos). Para empresas recém-cadastradas, sugestões ficam
    indisponíveis até a primeira apuração + folha rodar.
    """

    http_status = 422


class FatorRNaoAplicavel(DomainError):
    """Anexo declarado não é III nem V — Fator R não muda anexo efetivo.

    Empresas em Anexos I, II e IV (LC 123 art. 18 §5º) não têm dependência
    de folha/receita para alíquota.
    """

    http_status = 422


# ── AI Advisor — weekly digest (Sprint 15 PR3) ───────────────────────────────


class DigestJaGeradoNaSemana(DomainError):
    """Já existe digest ativo para (empresa, semana_iso) — exposto como 409
    quando o caller não passa ``forcar=True`` (idempotência §8.9).
    """

    http_status = 409


class EmpresaSemWhatsapp(DomainError):
    """Empresa não tem ``whatsapp_phone`` cadastrado — digest não pode ser enviado.

    Geração do digest ainda funciona (snapshot persistido com texto pronto);
    apenas a etapa de envio fica bloqueada até o telefone ser cadastrado.
    """

    http_status = 422


class LlmIndisponivelDigest(DomainError):
    """LLM falhou e fallback ao template determinístico também falhou.

    Cenário extremo (template puro não deveria falhar nunca). Caller decide
    se aborta ou re-tenta no próximo ciclo do beat.
    """

    http_status = 503


# ── AI Advisor — envio do digest WhatsApp (Sprint 15.5) ──────────────────────


class DigestJaEnviado(DomainError):
    """Tentativa de re-enviar digest com ``status='enviado'`` — idempotência §8.9.

    Exposto como 409. Não viola §8.2 (status é metadado de transmissão,
    não fato fiscal); apenas sinaliza ao caller que a ação já ocorreu.
    """

    http_status = 409


class EnvioWhatsappFalhou(DomainError):
    """Meta WhatsApp rejeitou o envio do digest (after retries + backoff).

    O service incrementa ``tentativas_envio`` e mantém ``status='preparado'``
    até atingir o limite (5 ciclos), quando promove para ``status='falhou'``.
    Re-tentativa automática no próximo ciclo do beat (segunda 06:30 BR).
    """

    http_status = 502


# ── SPED (Sprint 16 PR1) ─────────────────────────────────────────────────────


class SpedJaGerado(DomainError):
    """Tentativa de re-gerar SPED ativo para mesma (empresa, tipo, período).

    Idempotência §8.9: passar ``forcar=True`` para criar nova versão que
    supersede a anterior (snapshot imutável §8.2). Sem ``forcar``, devolve
    409 e mantém o arquivo atual.
    """

    http_status = 409


class SemDadosParaSped(DomainError):
    """Não há plano de contas + lançamentos contábeis no período pedido.

    ECD sem plano + sem lançamentos vira arquivo de zero utilidade —
    preferimos falhar explicitamente para o cliente entender que a
    contabilidade do ano ainda não foi escriturada.
    """

    http_status = 422


class EmpresaNaoElegivelEcd(DomainError):
    """MEI dispensado de ECD (LC 123/2006 art. 18-A §13 + IN RFB 2.003/2021).

    MEI mantém apenas o Livro Caixa simplificado. Tentativa de gerar ECD
    para MEI devolve 422 com explicação fiscal.
    """

    http_status = 422


class EmpresaNaoElegivelEfd(DomainError):
    """EFD-Contribuições é obrigatória apenas para LP / LR (IN RFB 1.252/2012).

    MEI e Simples Nacional são dispensados da EFD-Contribuições — a
    contrapartida do SN é a DEFIS (Sprint 6). Para EFD ICMS-IPI a
    elegibilidade depende de inscrição estadual (Sprint 17 PR2).
    """

    http_status = 422


class ArquivoSpedNaoEncontrado(DomainError):
    """ID inexistente, cross-tenant via RLS ou cross-empresa."""

    http_status = 404


# ── Painel admin de tabelas tributárias (Sprint 19.5 PR1) ────────────────────


class TipoTabelaDesconhecido(DomainError):
    """``tipo_tabela`` fora do conjunto aceito (inss/irrf/fgts/simples_nacional/
    presuncao_lp/icms_uf/cbs_ibs).

    Sprint 19.5 PR1. Devolve 422 com a lista dos 7 tipos válidos para o caller
    (admin humano postando vigência via API) corrigir o payload.
    """

    http_status = 422


class VigenciaTributariaInvalida(DomainError):
    """Validação §8.6 falhou no payload de uma nova vigência tributária.

    Sprint 19.5 PR1. Engloba todos os erros de pré-INSERT detectados pelos
    validadores puros em ``app/modules/tabelas_admin/validadores.py``:

      * Faixas não progressivas (``limite[n] <= limite[n-1]``).
      * Alíquotas fora de ``[0, 1]`` (rejeita "7,5" — exige "0.075").
      * ``valid_from`` anterior à vigência ativa (regressão temporal).
      * Primeira faixa de INSS/IRRF abaixo do salário mínimo do ano.
      * Heurística de plausibilidade (IRPJ presumido 8-32%, CSLL 9%, etc.).

    A mensagem identifica o campo específico que falhou — não é erro genérico.
    """

    http_status = 422


class VigenciaTributariaJaPostada(DomainError):
    """``idempotency_key`` colidiu com payload divergente — quase certamente
    erro do admin postando coisas diferentes com a mesma chave.

    Sprint 19.5 PR1. Idempotência §8.9: re-POST com mesma chave + mesmo
    payload devolve o log anterior (200, no-op). Mesma chave + payload
    diferente devolve 409 com esta exceção. Resolução: gerar nova
    ``idempotency_key`` ou ajustar o payload para bater com o original.
    """

    http_status = 409


class DouIndisponivel(DomainError):
    """DOU (Diário Oficial da União) não respondeu após retries.

    Sprint 19.5 PR3. O worker mensal ``tabelas.varrer_dou_mensal`` captura
    e segue silenciosamente — varredura é mensal, perder 1 ciclo não é
    fatal. API DOU é semi-pública sem SLA (pendência ``[externo]`` da sprint).
    """

    http_status = 503


class SugestaoVigenciaNaoEncontrada(DomainError):
    """ID de sugestão inexistente. Sprint 19.5 PR3."""

    http_status = 404


class SugestaoVigenciaForaDeFluxo(DomainError):
    """Transição de status inválida.

    Sprint 19.5 PR3. Aprovar/rejeitar sugestão que já está ``aprovada``,
    ``rejeitada`` ou ``expirada`` cai aqui. Máquina de estados linear:
    ``pendente`` → ``aprovada`` | ``rejeitada`` | ``expirada``. Sem volta.
    """

    http_status = 409


# ── eSocial transmissão real — Sprint 19.7 PR2 (#13) ─────────────────────────


class EsocialEventoNaoEncontrado(DomainError):
    """ID do evento eSocial inexistente para o tenant atual."""

    http_status = 404


class EsocialTransmissaoDesativada(DomainError):
    """Tentativa de transmitir com flag ESOCIAL_TRANSMISSAO_ATIVA=false.

    §8.12 — transmissão é ato consciente. Service para com 412 quando
    admin tenta forçar o envio sem flip explícito da flag.
    """

    http_status = 412


class EsocialAssinaturaIndisponivel(DomainError):
    """Cert A1 ausente ou grupo opt-in 'esocial' não instalado."""

    http_status = 412


class EsocialErroAPI(DomainError):
    """eSocial respondeu com 4xx/5xx ou XML inválido após retries."""

    http_status = 502


class EsocialLoteInvalido(DomainError):
    """Lote vazio, com tipo inválido ou excedendo limite oficial."""

    http_status = 422


# ── DARF LP — guias de pagamento (Sprint 20 PR1) ──────────────────────────────


class DarfLpJaGerada(DomainError):
    """DARF LP já gerada para (empresa, código de receita, competência).

    Idempotência §8.9: re-POST com mesma (empresa, codigo_receita, competencia)
    devolve 409. Para forçar nova versão, cancele a guia existente primeiro.
    """

    http_status = 409


class ApuracaoLpNaoEncontrada(DomainError):
    """Apuração LP necessária para gerar DARF não encontrada.

    DARF só pode ser gerada após a apuração fiscal do período (IRPJ/CSLL
    trimestral ou PIS/Cofins mensal). Crie a apuração primeiro via
    POST /v1/empresas/{eid}/lp/{tipo}.
    """

    http_status = 404


class GuiaPagamentoNaoEncontrada(DomainError):
    """Guia de pagamento não encontrada ou cross-tenant (RLS §8.1)."""

    http_status = 404


# ── Checklist LP (Sprint 20 PR2) ──────────────────────────────────────────────


class ChecklistLpNaoConcluido(DomainError):
    """Tentativa de fechar trimestre LP com obrigações pendentes/atrasadas.

    O endpoint POST /fechar valida que todos os itens estão 'ok'.
    """

    http_status = 409
