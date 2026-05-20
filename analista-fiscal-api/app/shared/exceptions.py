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


class CnpjJaCadastrado(DomainError):
    http_status = 409


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
    """Pluggy retornou erro HTTP inesperado (4xx/5xx não tratado)."""

    http_status = 502


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
    """Tentativa de encerrar competência já encerrada, ou lançar em mês fechado."""

    http_status = 409


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
