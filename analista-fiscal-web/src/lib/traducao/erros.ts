/**
 * lib/traducao/erros.ts
 *
 * Mapa central: código de erro de domínio (backend DomainError) → frase humana.
 * Formato de cada entrada: { oqueSePasso, oqueFazer, acaoPrimaria? }
 *
 * Regras:
 *  - Nunca expor stack trace, código HTTP ou nome técnico da exceção.
 *  - Sempre: "o que houve em PT simples" + "o que fazer" + botão/ação opcional.
 *  - Fallback genérico cobre erros não mapeados.
 */

// ─── Tipos ────────────────────────────────────────────────────────────────────

export interface EntradaErro {
  /** O que houve — frase curta em PT simples. */
  oqueSePasso: string;
  /** O que o usuário pode fazer agora. */
  oqueFazer: string;
  /** Rótulo do botão de ação (opcional). Se ausente, exibir só "Tentar de novo". */
  rotuloBotao?: string;
  /** Rota para navegar ao clicar no botão de ação (opcional). */
  rotaAcao?: string;
}

// ─── Fallback genérico ────────────────────────────────────────────────────────

export const ERRO_GENERICO: EntradaErro = {
  oqueSePasso: "Algo inesperado aconteceu.",
  oqueFazer: "Seus dados estão salvos. Tente de novo em alguns instantes.",
  rotuloBotao: "Tentar de novo",
};

// ─── Mapa de erros ────────────────────────────────────────────────────────────

const MAPA_ERROS: Record<string, EntradaErro> = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  TokenInvalido: {
    oqueSePasso: "Sua sessão expirou.",
    oqueFazer: "Faça login novamente para continuar.",
    rotuloBotao: "Fazer login",
    rotaAcao: "/login",
  },
  CredenciaisInvalidas: {
    oqueSePasso: "E-mail ou senha incorretos.",
    oqueFazer: "Confira seus dados e tente de novo.",
    rotuloBotao: "Tentar de novo",
  },
  SemPermissao: {
    oqueSePasso: "Você não tem permissão para fazer isso.",
    oqueFazer: "Se achar que é um engano, fale com o administrador da conta.",
  },

  // ── Empresa ───────────────────────────────────────────────────────────────
  EmpresaNaoEncontrada: {
    oqueSePasso: "Empresa não encontrada.",
    oqueFazer: "Verifique se você está na conta certa.",
  },
  CnpjInvalido: {
    oqueSePasso: "O CNPJ informado está incorreto.",
    oqueFazer: "Confira os 14 dígitos e tente de novo.",
    rotuloBotao: "Corrigir CNPJ",
  },
  CnpjJaCadastrado: {
    oqueSePasso: "Esse CNPJ já está cadastrado no sistema.",
    oqueFazer: "Faça login com a conta existente ou entre em contato com o suporte.",
    rotuloBotao: "Fazer login",
    rotaAcao: "/login",
  },
  CnpjNaoEncontrado: {
    oqueSePasso: "CNPJ não encontrado na Receita Federal.",
    oqueFazer: "Confira o número digitado. Se estiver correto, tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  MunicipioIbgeAusente: {
    oqueSePasso: "O município da empresa não está configurado.",
    oqueFazer: "Acesse as configurações e informe o município para poder emitir notas.",
    rotuloBotao: "Ir para configurações",
    rotaAcao: "/configuracoes/empresa",
  },

  // ── Fiscal ────────────────────────────────────────────────────────────────
  TabelaTributariaAusente: {
    oqueSePasso: "Não encontramos as tabelas de imposto para o período.",
    oqueFazer: "Entre em contato com o suporte — vamos resolver em breve.",
  },
  ApuracaoJaExiste: {
    oqueSePasso: "Já existe uma apuração para esse período.",
    oqueFazer: "Acesse a apuração já criada na tela fiscal.",
    rotuloBotao: "Ver apuração",
    rotaAcao: "/fiscal",
  },
  ApuracaoNaoEncontrada: {
    oqueSePasso: "Apuração não encontrada para esse período.",
    oqueFazer: "Verifique se o período está correto.",
  },
  RegimeIncompativel: {
    oqueSePasso: "Essa operação não é compatível com o regime tributário da empresa.",
    oqueFazer: "Confira o regime cadastrado nas configurações.",
    rotuloBotao: "Ver configurações",
    rotaAcao: "/configuracoes/empresa",
  },
  EmpresaForaSimplesNacional: {
    oqueSePasso: "Sua empresa ultrapassou o teto do Simples Nacional.",
    oqueFazer: "É necessário mudar de regime tributário. Fale com seu contador.",
  },
  FatorRObrigatorio: {
    oqueSePasso: "Para calcular o imposto, precisamos do total de salários pagos.",
    oqueFazer: "Informe a folha de pagamento dos últimos 12 meses.",
  },

  // ── Notas / NF-e ─────────────────────────────────────────────────────────
  XmlInvalido: {
    oqueSePasso: "O arquivo XML da nota fiscal está inválido.",
    oqueFazer: "Importe novamente ou verifique se o arquivo está correto.",
    rotuloBotao: "Tentar novamente",
  },
  DocumentoJaIngerido: {
    oqueSePasso: "Essa nota já foi importada anteriormente.",
    oqueFazer: "Verifique nas notas fiscais — ela já está no sistema.",
    rotuloBotao: "Ver notas",
    rotaAcao: "/notas",
  },
  DocumentoNaoEncontrado: {
    oqueSePasso: "Nota fiscal não encontrada.",
    oqueFazer: "Verifique a chave de acesso e tente de novo.",
  },
  NfseJaEmitida: {
    oqueSePasso: "Essa nota de serviço já foi emitida.",
    oqueFazer: "Consulte a nota já emitida na lista de notas fiscais.",
    rotuloBotao: "Ver notas",
    rotaAcao: "/notas",
  },

  // ── Integrações externas ──────────────────────────────────────────────────
  FocusNfeErro: {
    oqueSePasso: "Não conseguimos falar com o serviço de emissão de notas.",
    oqueFazer: "Seus dados foram salvos. Tente emitir de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  FocusNfeTimeout: {
    oqueSePasso: "O serviço de emissão de notas demorou demais para responder.",
    oqueFazer: "Tente de novo. Se o problema persistir, verifique se a nota foi emitida na lista.",
    rotuloBotao: "Ver notas",
    rotaAcao: "/notas",
  },
  BrasilApiIndisponivel: {
    oqueSePasso: "Não conseguimos consultar o CNPJ agora.",
    oqueFazer: "O serviço da Receita Federal está instável. Tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  SerproErro: {
    oqueSePasso: "Não conseguimos falar com o sistema do governo (SERPRO).",
    oqueFazer: "Tente de novo em alguns minutos. Se o problema persistir, fale com o suporte.",
    rotuloBotao: "Tentar de novo",
  },
  SerproTimeout: {
    oqueSePasso: "O sistema do governo demorou demais para responder.",
    oqueFazer: "Tente de novo em alguns instantes.",
    rotuloBotao: "Tentar de novo",
  },
  SerproCredencialAusente: {
    oqueSePasso: "Certificado digital não configurado.",
    oqueFazer: "Para consultar dados no governo, é preciso configurar o certificado digital da empresa.",
    rotuloBotao: "Configurar certificado",
    rotaAcao: "/configuracoes/certificado",
  },
  PluggyErro: {
    oqueSePasso: "Não conseguimos falar com o seu banco agora.",
    oqueFazer: "Tente sincronizar de novo. Se persistir, reconecte a conta bancária.",
    rotuloBotao: "Tentar de novo",
  },
  PluggyTimeout: {
    oqueSePasso: "O banco demorou para responder.",
    oqueFazer: "Tente sincronizar de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },

  // ── LLM / Assistente ─────────────────────────────────────────────────────
  LLMIndisponivel: {
    oqueSePasso: "O assistente está temporariamente indisponível.",
    oqueFazer: "Tente de novo em alguns instantes. Os dados da empresa estão seguros.",
    rotuloBotao: "Tentar de novo",
  },
  LLMRespostaInvalida: {
    oqueSePasso: "O assistente não conseguiu gerar uma resposta confiável.",
    oqueFazer: "Tente reformular sua pergunta ou tente de novo.",
    rotuloBotao: "Tentar de novo",
  },

  // ── Contábil ──────────────────────────────────────────────────────────────
  LancamentoInvalido: {
    oqueSePasso: "O lançamento contábil tem um problema.",
    oqueFazer: "Verifique se os valores de débito e crédito estão equilibrados.",
  },
  CompetenciaJaEncerrada: {
    oqueSePasso: "Esse mês já foi encerrado.",
    oqueFazer: "Não é possível alterar lançamentos em meses já encerrados.",
  },
  LancamentoEmMesEncerrado: {
    oqueSePasso: "Não é possível alterar esse lançamento.",
    oqueFazer: "O mês a que ele pertence já foi encerrado contabilmente.",
  },

  // ── Folha / Pessoal ───────────────────────────────────────────────────────
  FuncionarioNaoEncontrado: {
    oqueSePasso: "Funcionário não encontrado.",
    oqueFazer: "Verifique se ele está cadastrado na lista de funcionários.",
    rotuloBotao: "Ver funcionários",
    rotaAcao: "/pessoal/funcionarios",
  },
  FolhaJaFechada: {
    oqueSePasso: "Essa folha de pagamento já foi fechada.",
    oqueFazer: "Folhas fechadas não podem ser alteradas. Para correções, fale com seu contador.",
  },
  CpfInvalido: {
    oqueSePasso: "O CPF informado está incorreto.",
    oqueFazer: "Confira os 11 dígitos e tente de novo.",
  },
  CpfJaCadastrado: {
    oqueSePasso: "Esse CPF já está cadastrado para esta empresa.",
    oqueFazer: "Verifique se o funcionário já está na lista.",
    rotuloBotao: "Ver funcionários",
    rotaAcao: "/pessoal/funcionarios",
  },

  // ── Compliance / Certidões ────────────────────────────────────────────────
  CertidaoNaoEncontrada: {
    oqueSePasso: "Certidão não encontrada.",
    oqueFazer: "Tente buscar a certidão novamente.",
    rotuloBotao: "Tentar de novo",
  },
  CertidaoEmissaoFalhou: {
    oqueSePasso: "Não conseguimos emitir a certidão agora.",
    oqueFazer: "O serviço do governo pode estar instável. Tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },

  // ── Reforma Tributária ────────────────────────────────────────────────────
  SemApuracoesDoPeriodo: {
    oqueSePasso: "Não há dados suficientes para simular a Reforma Tributária.",
    oqueFazer: "A simulação fica disponível após a primeira apuração fiscal ser registrada.",
  },

  // ── Erros de rede / genéricos HTTP ────────────────────────────────────────
  http_401: {
    oqueSePasso: "Sua sessão expirou.",
    oqueFazer: "Faça login novamente para continuar.",
    rotuloBotao: "Fazer login",
    rotaAcao: "/login",
  },
  http_403: {
    oqueSePasso: "Você não tem permissão para ver isso.",
    oqueFazer: "Se achar que é um engano, fale com o administrador da conta.",
  },
  http_404: {
    oqueSePasso: "Essa informação não foi encontrada.",
    oqueFazer: "Ela pode ter sido removida. Tente voltar para a tela anterior.",
  },
  http_409: {
    oqueSePasso: "Esse registro já existe.",
    oqueFazer: "Verifique se o item já está cadastrado antes de criar um novo.",
  },
  http_422: {
    oqueSePasso: "Os dados enviados estão incorretos.",
    oqueFazer: "Confira os campos e tente de novo.",
  },
  http_429: {
    oqueSePasso: "Muitas tentativas em pouco tempo.",
    oqueFazer: "Aguarde alguns segundos e tente de novo.",
    rotuloBotao: "Tentar de novo",
  },
  http_500: {
    oqueSePasso: "Nosso servidor encontrou um problema.",
    oqueFazer: "Seus dados estão salvos. Estamos resolvendo — tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  http_502: {
    oqueSePasso: "Não conseguimos falar com o serviço externo agora.",
    oqueFazer: "O serviço pode estar instável. Tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  http_503: {
    oqueSePasso: "O serviço está temporariamente indisponível.",
    oqueFazer: "Estamos cientes. Tente de novo em alguns minutos.",
    rotuloBotao: "Tentar de novo",
  },
  http_504: {
    oqueSePasso: "O servidor demorou demais para responder.",
    oqueFazer: "Tente de novo em alguns instantes.",
    rotuloBotao: "Tentar de novo",
  },
  invalid_json: {
    oqueSePasso: "A resposta do servidor veio em formato inesperado.",
    oqueFazer: "Tente recarregar a página.",
    rotuloBotao: "Recarregar",
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Traduz um código de erro de domínio para uma mensagem amigável.
 * Aceita:
 *  - Nome da classe de exceção do backend: "CnpjInvalido"
 *  - Código HTTP genérico: "http_404"
 *  - Mensagem de rede: "invalid_json"
 *
 * Nunca retorna `undefined` — sempre devolve o fallback genérico.
 */
export function traduzirErro(codigoOuMensagem: string): EntradaErro {
  // Tentativa 1: correspondência exata
  const direto = MAPA_ERROS[codigoOuMensagem];
  if (direto) return direto;

  // Tentativa 2: código HTTP implícito (e.g. "http_404" a partir de status 404)
  const httpKey = `http_${codigoOuMensagem}`;
  const viaHttp = MAPA_ERROS[httpKey];
  if (viaHttp) return viaHttp;

  // Fallback
  return ERRO_GENERICO;
}

/**
 * Converte um status HTTP numérico para uma `EntradaErro`.
 */
export function traduzirErroHttp(status: number): EntradaErro {
  return MAPA_ERROS[`http_${status}`] ?? ERRO_GENERICO;
}
