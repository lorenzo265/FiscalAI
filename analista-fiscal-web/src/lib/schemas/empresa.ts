import { z } from "zod";

export const regimeTributarioSchema = z.enum([
  "MEI",
  "SIMPLES_NACIONAL",
  "LUCRO_PRESUMIDO",
  "LUCRO_REAL",
]);
export type RegimeTributario = z.infer<typeof regimeTributarioSchema>;

export const setorAtividadeSchema = z.enum([
  "COMERCIO",
  "INDUSTRIA",
  "SERVICOS",
  "MISTO",
]);
export type SetorAtividade = z.infer<typeof setorAtividadeSchema>;

export const anexoSimplesSchema = z.enum(["I", "II", "III", "IV", "V"]);
export type AnexoSimples = z.infer<typeof anexoSimplesSchema>;

export const socioSchema = z.object({
  cpf: z.string(),
  nome: z.string(),
  participacao: z.number().min(0).max(100),
  isAdministrador: z.boolean(),
});
export type Socio = z.infer<typeof socioSchema>;

export const certificadoA1Schema = z.object({
  nomeArquivo: z.string(),
  validade: z.string(),
  mock: z.literal(true),
});
export type CertificadoA1 = z.infer<typeof certificadoA1Schema>;

export const bancoConectadoSchema = z.object({
  id: z.string(),
  banco: z.string(),
  apelido: z.string(),
  saldo: z.number(),
  ultimaSync: z.string(),
});
export type BancoConectado = z.infer<typeof bancoConectadoSchema>;

export const empresaSchema = z.object({
  id: z.string(),
  cnpj: z.string().regex(/^\d{14}$/),
  razaoSocial: z.string(),
  nomeFantasia: z.string().optional(),
  regime: regimeTributarioSchema,
  anexoSimples: anexoSimplesSchema.optional(),
  setor: setorAtividadeSchema,
  cnae: z.string(),
  uf: z.string().length(2),
  municipio: z.string(),
  inscricaoEstadual: z.string().optional(),
  inscricaoMunicipal: z.string().optional(),
  faturamento12m: z.number(),
  socios: z.array(socioSchema),
  certificadoA1: certificadoA1Schema.optional(),
  bancosConectados: z.array(bancoConectadoSchema),
  modulosAtivos: z.array(z.string()),
  criadoEm: z.string(),
});
export type Empresa = z.infer<typeof empresaSchema>;
