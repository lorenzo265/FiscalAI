import { z } from "zod";

export const tomSchema = z.enum(["ok", "warn", "error", "info", "neutral"]);
export type Tom = z.infer<typeof tomSchema>;

export const acaoSchema = z.object({
  label: z.string(),
  rota: z.string(),
});
export type Acao = z.infer<typeof acaoSchema>;

export const alertaFiscalSchema = z.object({
  id: z.string(),
  tom: z.enum(["info", "warn", "error"]),
  titulo: z.string(),
  descricao: z.string(),
  acao: acaoSchema.optional(),
});
export type AlertaFiscal = z.infer<typeof alertaFiscalSchema>;

export const composicaoTributoSchema = z.object({
  tributo: z.string(),
  apelido: z.string(),
  valor: z.number(),
  percentual: z.number(),
});
export type ComposicaoTributo = z.infer<typeof composicaoTributoSchema>;

export const apuracaoFiscalSchema = z.object({
  periodo: z.object({ ano: z.number(), mes: z.number() }),
  faturamentoMes: z.number(),
  faturamento12m: z.number(),
  sublimiteEstadual: z.number(),
  tetoSimples: z.number(),
  fatorR: z
    .object({
      valor: z.number(),
      anexoAtual: z.enum(["III", "V"]),
      atencao: z.boolean(),
    })
    .optional(),
  aliquotaEfetiva: z.number(),
  aliquotaNominal: z.number(),
  faixa: z.number(),
  valorDAS: z.number(),
  vencimento: z.string(),
  status: z.enum(["calculado", "pago", "atrasado", "em_aberto"]),
  composicao: z.array(composicaoTributoSchema),
  alertas: z.array(alertaFiscalSchema),
});
export type ApuracaoFiscal = z.infer<typeof apuracaoFiscalSchema>;

export const fiscalHealthSchema = z.object({
  score: z.number().min(0).max(100),
  tom: z.enum(["ok", "warn", "error"]),
  titulo: z.string(),
  descricao: z.string(),
  componentes: z.array(
    z.object({
      categoria: z.enum([
        "obrigacoes_em_dia",
        "certidoes_validas",
        "sem_intimacoes",
        "fator_r_seguro",
        "sublimite_seguro",
        "conciliacao_em_dia",
      ]),
      label: z.string(),
      pontuacao: z.number().min(0).max(100),
      tom: z.enum(["ok", "warn", "error"]),
      mensagem: z.string(),
    })
  ),
  alertasPrioritarios: z.array(alertaFiscalSchema).max(3),
  proximaObrigacao: z.object({
    titulo: z.string(),
    descricao: z.string(),
    vencimento: z.string(),
    acao: acaoSchema,
  }),
});
export type FiscalHealth = z.infer<typeof fiscalHealthSchema>;

export const historicoMesSchema = z.object({
  ano: z.number(),
  mes: z.number(),
  rotulo: z.string(),
  receita: z.number(),
  imposto: z.number(),
});
export type HistoricoMes = z.infer<typeof historicoMesSchema>;

export const historicoFiscalSchema = z.array(historicoMesSchema);
