import { z } from "zod";

export const tipoCertidaoSchema = z.enum([
  "CND_FEDERAL",
  "CRF_FGTS",
  "CNDT_TRABALHISTA",
  "CND_ESTADUAL",
  "CND_MUNICIPAL",
]);
export type TipoCertidao = z.infer<typeof tipoCertidaoSchema>;

export const TIPO_CERTIDAO_LABEL: Record<TipoCertidao, string> = {
  CND_FEDERAL: "CND Federal",
  CRF_FGTS: "CRF FGTS",
  CNDT_TRABALHISTA: "CNDT Trabalhista",
  CND_ESTADUAL: "CND Estadual",
  CND_MUNICIPAL: "CND Municipal",
};

export const TIPO_CERTIDAO_DESCRICAO: Record<TipoCertidao, string> = {
  CND_FEDERAL:
    "Certidão Negativa de Débitos relativos a tributos federais e à Dívida Ativa da União.",
  CRF_FGTS:
    "Certificado de Regularidade do FGTS — emitido pela Caixa Econômica Federal.",
  CNDT_TRABALHISTA:
    "Certidão Negativa de Débitos Trabalhistas — emitida pelo TST.",
  CND_ESTADUAL: "Certidão de regularidade fiscal estadual (ICMS).",
  CND_MUNICIPAL: "Certidão de regularidade municipal (ISS, IPTU).",
};

export const statusCertidaoSchema = z.enum([
  "vigente",
  "vence_em_breve",
  "vencida",
  "irregular",
]);
export type StatusCertidao = z.infer<typeof statusCertidaoSchema>;

export const certidaoSchema = z.object({
  id: z.string(),
  tipo: tipoCertidaoSchema,
  numero: z.string(),
  emitidaEm: z.string(),
  vencimento: z.string(),
  status: statusCertidaoSchema,
  emitidaPor: z.string(),
  observacao: z.string().optional(),
});
export type Certidao = z.infer<typeof certidaoSchema>;
export const certidoesSchema = z.array(certidaoSchema);

export const orgaoIntimacaoSchema = z.enum([
  "RFB",
  "PGFN",
  "ESTADO",
  "MUNICIPIO",
  "MTE",
  "INSS",
]);
export type OrgaoIntimacao = z.infer<typeof orgaoIntimacaoSchema>;

export const ORGAO_LABEL: Record<OrgaoIntimacao, string> = {
  RFB: "Receita Federal",
  PGFN: "PGFN",
  ESTADO: "Sefaz Estadual",
  MUNICIPIO: "Prefeitura",
  MTE: "Ministério do Trabalho",
  INSS: "INSS",
};

export const statusIntimacaoSchema = z.enum([
  "nova",
  "lida",
  "em_resposta",
  "respondida",
  "encerrada",
]);
export type StatusIntimacao = z.infer<typeof statusIntimacaoSchema>;

export const intimacaoSchema = z.object({
  id: z.string(),
  protocolo: z.string(),
  orgao: orgaoIntimacaoSchema,
  assunto: z.string(),
  texto: z.string(),
  recebidoEm: z.string(),
  prazoResposta: z.string(),
  status: statusIntimacaoSchema,
  enviadoContador: z.boolean().default(false),
});
export type Intimacao = z.infer<typeof intimacaoSchema>;
export const intimacoesSchema = z.array(intimacaoSchema);

export const statusParcelamentoSchema = z.enum([
  "ativo",
  "rescindido",
  "quitado",
]);
export type StatusParcelamento = z.infer<typeof statusParcelamentoSchema>;

export const parcelamentoSchema = z.object({
  id: z.string(),
  numero: z.string(),
  orgao: orgaoIntimacaoSchema,
  assunto: z.string(),
  parcelaAtual: z.number().int(),
  totalParcelas: z.number().int(),
  valorParcela: z.number(),
  saldoDevedor: z.number(),
  proximoVencimento: z.string(),
  status: statusParcelamentoSchema,
});
export type Parcelamento = z.infer<typeof parcelamentoSchema>;
export const parcelamentosSchema = z.array(parcelamentoSchema);

export const compliancePainelSchema = z.object({
  certidoesVigentes: z.number().int(),
  certidoesTotal: z.number().int(),
  intimacoesAbertas: z.number().int(),
  intimacoesTotal: z.number().int(),
  parcelamentosAtivos: z.number().int(),
  cnpjAtivo: z.boolean(),
  proximaCertidaoVencimento: z.string().nullable(),
});
export type CompliancePainel = z.infer<typeof compliancePainelSchema>;
