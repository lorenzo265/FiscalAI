import { z } from "zod";

export const periodoRelatorioSchema = z.object({
  ano: z.number().int(),
  mes: z.number().int().min(1).max(12),
  rotulo: z.string(),
});
export type PeriodoRelatorio = z.infer<typeof periodoRelatorioSchema>;

export const tipoLinhaDreSchema = z.enum([
  "secao",
  "linha",
  "subtotal",
  "total",
  "deducao",
  "margem",
]);
export type TipoLinhaDre = z.infer<typeof tipoLinhaDreSchema>;

export const linhaDreSchema = z.object({
  chave: z.string(),
  rotulo: z.string(),
  tipo: tipoLinhaDreSchema,
  // valores indexados pela posição em PeriodoRelatorio[] retornado
  valores: z.array(z.number()),
  // Formato. Margem mostra como percentual.
  formato: z.enum(["moeda", "percentual"]).default("moeda"),
});
export type LinhaDre = z.infer<typeof linhaDreSchema>;

export const dreComparativoSchema = z.object({
  periodos: z.array(periodoRelatorioSchema),
  linhas: z.array(linhaDreSchema),
});
export type DreComparativo = z.infer<typeof dreComparativoSchema>;

export const linhaBalancoSchema = z.object({
  codigo: z.string(),
  rotulo: z.string(),
  valor: z.number(),
  destaque: z.enum(["grupo", "subgrupo", "conta"]),
  nivel: z.number().int(),
});
export type LinhaBalanco = z.infer<typeof linhaBalancoSchema>;

export const balancoPatrimonialSchema = z.object({
  competencia: z.string(),
  ativo: z.array(linhaBalancoSchema),
  passivoEPl: z.array(linhaBalancoSchema),
  totalAtivo: z.number(),
  totalPassivo: z.number(),
  totalPl: z.number(),
  bate: z.boolean(),
  diferenca: z.number(),
});
export type BalancoPatrimonial = z.infer<typeof balancoPatrimonialSchema>;

export const tipoLinhaDfcSchema = z.enum([
  "secao",
  "linha",
  "subtotal",
  "total",
]);
export type TipoLinhaDfc = z.infer<typeof tipoLinhaDfcSchema>;

export const linhaDfcSchema = z.object({
  chave: z.string(),
  rotulo: z.string(),
  tipo: tipoLinhaDfcSchema,
  valor: z.number(),
});
export type LinhaDfc = z.infer<typeof linhaDfcSchema>;

export const dfcSchema = z.object({
  competencia: z.string(),
  saldoInicial: z.number(),
  saldoFinal: z.number(),
  linhas: z.array(linhaDfcSchema),
});
export type DFC = z.infer<typeof dfcSchema>;

export const sparkPointSchema = z.object({
  rotulo: z.string(),
  valor: z.number(),
});
export type SparkPoint = z.infer<typeof sparkPointSchema>;

export const direcaoIndicadorSchema = z.enum(["alta", "queda", "estavel"]);
export type DirecaoIndicador = z.infer<typeof direcaoIndicadorSchema>;

export const formatoIndicadorSchema = z.enum([
  "percentual",
  "moeda",
  "decimal",
  "dias",
]);
export type FormatoIndicador = z.infer<typeof formatoIndicadorSchema>;

export const tomIndicadorSchema = z.enum(["ok", "warn", "error", "neutral"]);
export type TomIndicador = z.infer<typeof tomIndicadorSchema>;

export const indicadorSchema = z.object({
  chave: z.string(),
  titulo: z.string(),
  descricao: z.string(),
  valor: z.number(),
  formato: formatoIndicadorSchema,
  tom: tomIndicadorSchema,
  direcao: direcaoIndicadorSchema,
  variacao: z.number(),
  serie: z.array(sparkPointSchema),
});
export type Indicador = z.infer<typeof indicadorSchema>;

export const indicadoresSchema = z.array(indicadorSchema);
