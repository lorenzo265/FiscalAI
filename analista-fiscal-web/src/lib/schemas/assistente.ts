import { z } from "zod";

export const roleMensagemSchema = z.enum(["user", "assistant", "system"]);
export type RoleMensagem = z.infer<typeof roleMensagemSchema>;

export const tipoCitacaoSchema = z.enum([
  "apuracao",
  "guia",
  "nota",
  "lancamento",
  "extrato",
  "certidao",
  "intimacao",
  "folha",
  "agenda",
  // `fonte` = citação genérica vinda do backend (grafo de memória):
  // o backend só fornece `{fato_id, trecho_citado}`, sem categoria de domínio.
  "fonte",
]);
export type TipoCitacao = z.infer<typeof tipoCitacaoSchema>;

export const TIPO_CITACAO_LABEL: Record<TipoCitacao, string> = {
  apuracao: "Apuração",
  guia: "Guia",
  nota: "Nota fiscal",
  lancamento: "Lançamento",
  extrato: "Extrato bancário",
  certidao: "Certidão",
  intimacao: "Intimação",
  folha: "Folha",
  agenda: "Agenda",
  fonte: "Fonte",
};

export const citacaoSchema = z.object({
  tipo: tipoCitacaoSchema,
  rotulo: z.string(),
  rota: z.string().optional(),
});
export type Citacao = z.infer<typeof citacaoSchema>;

export const tipoBlocoSchema = z.enum(["texto", "stat", "lista", "alerta"]);
export type TipoBloco = z.infer<typeof tipoBlocoSchema>;

export const blocoStatSchema = z.object({
  tipo: z.literal("stat"),
  rotulo: z.string(),
  valor: z.string(),
  tom: z.enum(["ok", "warn", "error", "info", "neutral"]).default("neutral"),
});

export const blocoListaSchema = z.object({
  tipo: z.literal("lista"),
  titulo: z.string().optional(),
  itens: z.array(
    z.object({
      rotulo: z.string(),
      valor: z.string().optional(),
    })
  ),
});

export const blocoAlertaSchema = z.object({
  tipo: z.literal("alerta"),
  tom: z.enum(["ok", "warn", "error", "info"]),
  titulo: z.string(),
  descricao: z.string().optional(),
});

export const blocoTextoSchema = z.object({
  tipo: z.literal("texto"),
  texto: z.string(),
});

export const blocoSchema = z.discriminatedUnion("tipo", [
  blocoTextoSchema,
  blocoStatSchema,
  blocoListaSchema,
  blocoAlertaSchema,
]);
export type Bloco = z.infer<typeof blocoSchema>;

export const sugestaoSchema = z.object({
  texto: z.string(),
  pergunta: z.string(),
});
export type Sugestao = z.infer<typeof sugestaoSchema>;

export const mensagemAssistenteSchema = z.object({
  id: z.string(),
  role: roleMensagemSchema,
  texto: z.string(),
  blocos: z.array(blocoSchema).default([]),
  citacoes: z.array(citacaoSchema).default([]),
  sugestoes: z.array(sugestaoSchema).default([]),
  criadoEm: z.string(),
});
export type MensagemAssistente = z.infer<typeof mensagemAssistenteSchema>;
export const mensagensAssistenteSchema = z.array(mensagemAssistenteSchema);

// ── Contrato do backend (POST .../assistente/perguntar) ─────────────────────
// `fetchJson` aplica `toCamel` antes de validar; por isso os campos snake do
// backend (`fato_id`, `trecho_citado`, `encaminhar_marketplace`, …) chegam aqui
// em camelCase. Dinheiro/decimais (`custoUsd`) ficam como STRING — nunca number.

export const citacaoBackendSchema = z.object({
  fatoId: z.string(),
  trechoCitado: z.string(),
});
export type CitacaoBackend = z.infer<typeof citacaoBackendSchema>;

// Só tipos planos + `.nullable()/.optional()` (input == output) para o schema
// casar com `z.ZodSchema<RespostaAssistente>` em `fetchJson` — NÃO usar
// `.default()/.catch()` aqui (mudam o tipo de input e quebram a inferência).
// `custoUsd` permanece STRING (decimal NUMERIC — nunca number). Campos
// `metadata` (tokens/custo/latência) não são exibidos; mantidos por completude.
export const respostaAssistenteSchema = z.object({
  resposta: z.string(),
  citacoes: z.array(citacaoBackendSchema),
  encaminharMarketplace: z.boolean(),
  categoriaMarketplace: z.string().nullable(),
  categoriaMarketplaceSugerida: z.string().nullable().optional(),
  parceirosSugeridos: z.array(z.unknown()).optional(),
  providerUsado: z.string(),
  tokensInput: z.number(),
  tokensOutput: z.number(),
  tokensCached: z.number(),
  custoUsd: z.string(),
  latenciaMs: z.number(),
  empresaId: z.string(),
});
export type RespostaAssistente = z.infer<typeof respostaAssistenteSchema>;

export const SUGESTOES_INICIAIS: Sugestao[] = [
  { texto: "Quanto pago de DAS?", pergunta: "Quanto pago de DAS este mês?" },
  { texto: "Como está meu fluxo?", pergunta: "Como está meu fluxo de caixa?" },
  { texto: "Tem alguma intimação?", pergunta: "Tem alguma intimação aberta?" },
  { texto: "Vale virar fator R?", pergunta: "Vale a pena migrar pro fator R?" },
];
