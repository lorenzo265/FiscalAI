import { z } from "zod";

export const naturezaContaSchema = z.enum([
  "ativo",
  "passivo",
  "patrimonio_liquido",
  "receita",
  "despesa",
  "resultado",
]);
export type NaturezaConta = z.infer<typeof naturezaContaSchema>;

export const grupoContaSchema = z.enum([
  "ativo_circulante",
  "ativo_nao_circulante",
  "passivo_circulante",
  "passivo_nao_circulante",
  "patrimonio_liquido",
  "receita_operacional",
  "receita_nao_operacional",
  "deducao_receita",
  "custo",
  "despesa_operacional",
  "despesa_financeira",
  "resultado",
]);
export type GrupoConta = z.infer<typeof grupoContaSchema>;

export const contaContabilSchema = z.object({
  codigo: z.string(),
  pai: z.string().nullable(),
  nome: z.string(),
  natureza: naturezaContaSchema,
  grupo: grupoContaSchema,
  analitica: z.boolean(),
  nivel: z.number().int().min(1),
});
export type ContaContabil = z.infer<typeof contaContabilSchema>;

export const origemLancamentoSchema = z.enum([
  "nf_saida",
  "nf_entrada",
  "bancario",
  "folha",
  "manual",
  "fiscal",
  "encerramento",
]);
export type OrigemLancamento = z.infer<typeof origemLancamentoSchema>;

export const lancamentoContabilSchema = z.object({
  id: z.string(),
  data: z.string(),
  contaDebito: z.string(),
  contaCredito: z.string(),
  valor: z.number().nonnegative(),
  historico: z.string(),
  origem: origemLancamentoSchema,
  origemRefId: z.string().optional(),
  confianca: z.number().min(0).max(1).default(1),
  criadoEm: z.string(),
});
export type LancamentoContabil = z.infer<typeof lancamentoContabilSchema>;

export const lancamentosContabeisSchema = z.array(lancamentoContabilSchema);

export interface LinhaBalancete {
  conta: ContaContabil;
  saldoAnterior: number;
  debitos: number;
  creditos: number;
  saldoAtual: number;
  filhos: LinhaBalancete[];
}
