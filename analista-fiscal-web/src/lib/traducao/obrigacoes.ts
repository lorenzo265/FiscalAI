/**
 * lib/traducao/obrigacoes.ts
 *
 * Mapa central tipado: sigla fiscal → linguagem do dono de PME.
 * Padrão: frase principal em PT, termo técnico apenas em `termoTecnico`
 * (para "ver detalhe técnico" e para contadores).
 *
 * Uso:
 *   import { OBRIGACOES, TRIBUTOS, OUTROS, traduzirObrigacao } from "@/lib/traducao/obrigacoes";
 *   const { titulo, descricaoCurta } = OBRIGACOES.DAS;
 */

// ─── Tipos ────────────────────────────────────────────────────────────────────

export interface EntradaObrigacao {
  /** Texto principal exibido ao dono de PME. Sempre em PT claro. */
  titulo: string;
  /** Uma frase de contexto (sem jargão). */
  descricaoCurta: string;
  /** A sigla técnica — exibida apenas em <abbr> ou "ver detalhe técnico". */
  termoTecnico: string;
}

export interface EntradaTributo {
  /** Texto principal exibido ao dono de PME. */
  titulo: string;
  /** Aposto fixo — usado ao lado da sigla em contexto de health score etc. */
  aposto: string;
  /** A sigla técnica. */
  termoTecnico: string;
}

export interface EntradaFatorR {
  titulo: string;
  descricaoCurta: string;
  /** Explica o efeito, não o mecanismo. */
  efeito: string;
  termoTecnico: string;
}

export interface EntradaAnexo {
  titulo: string;
  descricaoCurta: string;
  termoTecnico: string;
}

// ─── Obrigações principais ────────────────────────────────────────────────────

export const OBRIGACOES = {
  DAS: {
    titulo: "Guia mensal de impostos",
    descricaoCurta: "O boleto único que reúne todos os impostos do Simples Nacional no mês.",
    termoTecnico: "DAS",
  },
  PGDAS_D: {
    titulo: "Declaração do faturamento do mês",
    descricaoCurta: "Você informa quanto faturou e o sistema calcula o imposto a pagar.",
    termoTecnico: "PGDAS-D",
  },
  DEFIS: {
    titulo: "Declaração anual da empresa",
    descricaoCurta: "Declaração anual obrigatória com o resumo fiscal do ano para empresas do Simples Nacional.",
    termoTecnico: "DEFIS",
  },
  ESOCIAL: {
    titulo: "Informações dos funcionários ao governo",
    descricaoCurta: "Registra admissões, demissões, férias e folha de pagamento na plataforma do governo.",
    termoTecnico: "eSocial",
  },
  DCTFWEB: {
    titulo: "Declaração dos impostos da folha",
    descricaoCurta: "Declara ao governo as contribuições previdenciárias e o imposto de renda retido na folha de pagamento.",
    termoTecnico: "DCTFWeb",
  },
  DCTF: {
    titulo: "Declaração de débitos tributários",
    descricaoCurta: "Informa à Receita Federal os impostos federais devidos.",
    termoTecnico: "DCTF",
  },
  DASN_SIMEI: {
    titulo: "Declaração anual do MEI",
    descricaoCurta: "Declaração obrigatória que o MEI envia uma vez por ano informando o faturamento.",
    termoTecnico: "DASN-SIMEI",
  },
  REINF: {
    titulo: "Declaração de retenções sobre serviços",
    descricaoCurta: "Declara ao governo os impostos retidos quando sua empresa paga por serviços com retenção obrigatória (ex.: limpeza, segurança, TI contratados de outras empresas).",
    termoTecnico: "EFD-Reinf",
  },
  SPED_ECD: {
    titulo: "Escrituração contábil digital",
    descricaoCurta: "Envio digital da contabilidade da empresa para a Receita Federal.",
    termoTecnico: "SPED ECD",
  },
  SPED_ECF: {
    titulo: "Escrituração fiscal digital do imposto de renda",
    descricaoCurta: "Declaração digital do imposto de renda da empresa (Lucro Presumido/Real).",
    termoTecnico: "SPED ECF",
  },
  GFIP: {
    titulo: "Declaração de FGTS e previdência",
    descricaoCurta: "Declaração das contribuições previdenciárias e do FGTS. Substituída pelo eSocial/DCTFWeb para quem está no novo sistema.",
    termoTecnico: "GFIP",
  },
} satisfies Record<string, EntradaObrigacao>;

export type ChaveObrigacao = keyof typeof OBRIGACOES;

// ─── Tributos do health score ─────────────────────────────────────────────────

export const TRIBUTOS = {
  ICMS: {
    titulo: "Imposto estadual sobre vendas",
    aposto: "imposto estadual sobre vendas",
    termoTecnico: "ICMS",
  },
  ISS: {
    titulo: "Imposto municipal sobre serviços",
    aposto: "imposto municipal sobre serviços",
    termoTecnico: "ISS",
  },
  INSS: {
    titulo: "Contribuição da previdência",
    aposto: "contribuição da previdência",
    termoTecnico: "INSS",
  },
  FGTS: {
    titulo: "Fundo do funcionário",
    aposto: "fundo do funcionário",
    termoTecnico: "FGTS",
  },
  IRPJ: {
    titulo: "Imposto de renda da empresa",
    aposto: "imposto de renda PJ",
    termoTecnico: "IRPJ",
  },
  CSLL: {
    titulo: "Contribuição sobre o lucro",
    aposto: "contribuição sobre lucro",
    termoTecnico: "CSLL",
  },
  PIS: {
    titulo: "Contribuição sobre faturamento (PIS)",
    aposto: "contribuição sobre faturamento",
    termoTecnico: "PIS",
  },
  COFINS: {
    titulo: "Contribuição sobre faturamento (Cofins)",
    aposto: "contribuição sobre faturamento",
    termoTecnico: "Cofins",
  },
  CPP: {
    titulo: "INSS patronal (parte da empresa)",
    aposto: "INSS patronal",
    termoTecnico: "CPP",
  },
  CBS: {
    titulo: "Contribuição federal sobre bens e serviços",
    aposto: "contribuição federal unificada (Reforma Tributária)",
    termoTecnico: "CBS",
  },
  IBS: {
    titulo: "Imposto estadual/municipal sobre bens e serviços",
    aposto: "imposto subnacional unificado (Reforma Tributária)",
    termoTecnico: "IBS",
  },
} satisfies Record<string, EntradaTributo>;

export type ChaveTributo = keyof typeof TRIBUTOS;

// ─── Fator R ──────────────────────────────────────────────────────────────────

export const FATOR_R: EntradaFatorR = {
  titulo: "Alíquota menor por ter folha de pagamento",
  descricaoCurta: "Se sua folha de pagamento representar pelo menos 28% do que você fatura, você se enquadra em uma faixa de imposto menor.",
  efeito:
    "Quando sua folha de pagamento ultrapassa 28% do faturamento dos últimos 12 meses, você paga a alíquota menor (Anexo III em vez do Anexo V).",
  termoTecnico: "Fator R",
};

// ─── Anexos do Simples Nacional ───────────────────────────────────────────────

export const ANEXOS = {
  I: {
    titulo: "Comércio",
    descricaoCurta: "Categoria do Simples Nacional para empresas que vendem produtos.",
    termoTecnico: "Anexo I",
  },
  II: {
    titulo: "Indústria",
    descricaoCurta: "Categoria do Simples Nacional para empresas que fabricam produtos.",
    termoTecnico: "Anexo II",
  },
  III: {
    titulo: "Serviços com alíquota menor",
    descricaoCurta: "Categoria do Simples Nacional para prestadores de serviço que têm folha de pagamento robusta (Fator R ≥ 28%).",
    termoTecnico: "Anexo III",
  },
  IV: {
    titulo: "Serviços especiais",
    descricaoCurta: "Categoria do Simples Nacional para atividades como construção civil, vigilância e limpeza. Não é afetado pelo Fator R.",
    termoTecnico: "Anexo IV",
  },
  V: {
    titulo: "Serviços com alíquota maior",
    descricaoCurta: "Categoria do Simples Nacional para prestadores de serviço com folha de pagamento menor que 28% do faturamento.",
    termoTecnico: "Anexo V",
  },
} satisfies Record<string, EntradaAnexo>;

export type ChaveAnexo = keyof typeof ANEXOS;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Retorna a entrada de obrigação ou `undefined` se a sigla não for reconhecida.
 * Aceita variações como "PGDAS-D", "pgdas-d", "PGDAS_D".
 */
export function traduzirObrigacao(sigla: string): EntradaObrigacao | undefined {
  const chave = sigla.toUpperCase().replace(/-/g, "_") as ChaveObrigacao;
  return OBRIGACOES[chave];
}

/**
 * Retorna a entrada de tributo ou `undefined` se a sigla não for reconhecida.
 */
export function traduzirTributo(sigla: string): EntradaTributo | undefined {
  const chave = sigla.toUpperCase() as ChaveTributo;
  return TRIBUTOS[chave];
}

/**
 * Retorna o aposto de um tributo — ex.: "ICMS" → "imposto estadual sobre vendas".
 * Se não encontrado, devolve a própria sigla (fallback seguro).
 */
export function apostoTributo(sigla: string): string {
  return traduzirTributo(sigla)?.aposto ?? sigla;
}

/**
 * Retorna o titulo PT de uma obrigação.
 * Se não encontrado, devolve a sigla original (nunca vaza código cru).
 */
export function tituloObrigacao(sigla: string): string {
  return traduzirObrigacao(sigla)?.titulo ?? sigla;
}
