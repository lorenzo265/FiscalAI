import { z } from "zod";

export const tipoNotaSchema = z.enum(["entrada", "saida"]);
export type TipoNota = z.infer<typeof tipoNotaSchema>;

export const statusNotaSchema = z.enum([
  "rascunho",
  "emitida",
  "autorizada",
  "rejeitada",
  "cancelada",
  "denegada",
]);
export type StatusNota = z.infer<typeof statusNotaSchema>;

export const statusManifestoSchema = z.enum([
  "pendente_manifesto",
  "ciencia",
  "confirmada",
  "desconhecida",
  "nao_realizada",
]);
export type StatusManifesto = z.infer<typeof statusManifestoSchema>;

export const formaPagamentoSchema = z.enum([
  "dinheiro",
  "pix",
  "boleto",
  "cartao_credito",
  "cartao_debito",
  "transferencia",
  "outros",
]);
export type FormaPagamento = z.infer<typeof formaPagamentoSchema>;

export const tipoContraparteSchema = z.enum(["pj", "pf"]);
export type TipoContraparte = z.infer<typeof tipoContraparteSchema>;

export const enderecoSchema = z.object({
  logradouro: z.string(),
  numero: z.string(),
  complemento: z.string().optional(),
  bairro: z.string(),
  municipio: z.string(),
  uf: z.string().length(2),
  cep: z.string(),
});
export type Endereco = z.infer<typeof enderecoSchema>;

export const contraparteSchema = z.object({
  id: z.string(),
  tipo: tipoContraparteSchema,
  documento: z.string(),
  nome: z.string(),
  email: z.string().optional(),
  inscricaoEstadual: z.string().optional(),
  endereco: enderecoSchema.optional(),
});
export type Contraparte = z.infer<typeof contraparteSchema>;

export const produtoCatalogoSchema = z.object({
  id: z.string(),
  descricao: z.string(),
  unidade: z.string(),
  precoSugerido: z.number(),
  ncm: z.string(),
  cfop: z.string(),
  tipo: z.enum(["produto", "servico"]),
});
export type ProdutoCatalogo = z.infer<typeof produtoCatalogoSchema>;

export const itemNotaSchema = z.object({
  id: z.string(),
  produtoId: z.string().optional(),
  descricao: z.string(),
  unidade: z.string(),
  quantidade: z.number().positive(),
  valorUnitario: z.number().nonnegative(),
  valorTotal: z.number().nonnegative(),
  ncm: z.string(),
  cfop: z.string(),
  cstCsosn: z.string(),
  aliquotaIcms: z.number().optional(),
  aliquotaIss: z.number().optional(),
  aliquotaPis: z.number().optional(),
  aliquotaCofins: z.number().optional(),
  impostoTotal: z.number().nonnegative(),
});
export type ItemNota = z.infer<typeof itemNotaSchema>;

export const totaisNotaSchema = z.object({
  produtos: z.number(),
  desconto: z.number(),
  frete: z.number(),
  icms: z.number(),
  iss: z.number(),
  pis: z.number(),
  cofins: z.number(),
  totalImpostos: z.number(),
  valorNota: z.number(),
});
export type TotaisNota = z.infer<typeof totaisNotaSchema>;

export const pagamentoNotaSchema = z.object({
  forma: formaPagamentoSchema,
  vencimento: z.string().optional(),
  parcelas: z.number().int().min(1).default(1),
});
export type PagamentoNota = z.infer<typeof pagamentoNotaSchema>;

export const notaFiscalSchema = z.object({
  id: z.string(),
  chave: z.string().length(44),
  numero: z.string(),
  serie: z.string(),
  tipo: tipoNotaSchema,
  status: statusNotaSchema,
  manifesto: statusManifestoSchema.optional(),
  emitidaEm: z.string(),
  cnpjEmitente: z.string(),
  razaoEmitente: z.string(),
  contraparte: contraparteSchema,
  itens: z.array(itemNotaSchema),
  totais: totaisNotaSchema,
  pagamento: pagamentoNotaSchema.optional(),
  observacao: z.string().optional(),
  protocoloAutorizacao: z.string().optional(),
  motivoRejeicao: z.string().optional(),
  canceladaEm: z.string().optional(),
  motivoCancelamento: z.string().optional(),
  cartasCorrecao: z
    .array(
      z.object({
        sequencia: z.number(),
        texto: z.string(),
        emitidaEm: z.string(),
      })
    )
    .default([]),
});
export type NotaFiscal = z.infer<typeof notaFiscalSchema>;

export const notasFiscaisSchema = z.array(notaFiscalSchema);
