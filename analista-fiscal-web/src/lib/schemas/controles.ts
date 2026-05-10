import { z } from "zod";

export const tipoTransacaoSchema = z.enum(["credito", "debito"]);
export type TipoTransacao = z.infer<typeof tipoTransacaoSchema>;

export const categoriaTransacaoSchema = z.enum([
  "receita_vendas",
  "recebimento_cliente",
  "pagamento_fornecedor",
  "folha_pagamento",
  "tributos",
  "tarifas_bancarias",
  "transferencia",
  "estorno",
  "rendimento",
  "outros",
]);
export type CategoriaTransacao = z.infer<typeof categoriaTransacaoSchema>;

export const CATEGORIA_LABEL: Record<CategoriaTransacao, string> = {
  receita_vendas: "Vendas",
  recebimento_cliente: "Recebimento cliente",
  pagamento_fornecedor: "Pagamento fornecedor",
  folha_pagamento: "Folha de pagamento",
  tributos: "Tributos e impostos",
  tarifas_bancarias: "Tarifas bancárias",
  transferencia: "Transferência",
  estorno: "Estorno",
  rendimento: "Rendimentos",
  outros: "Outros",
};

export const contaBancariaSchema = z.object({
  id: z.string(),
  bancoId: z.string(),
  bancoNome: z.string(),
  apelido: z.string(),
  agencia: z.string(),
  numero: z.string(),
  saldo: z.number(),
  cor: z.string(),
  textoCor: z.string(),
  iniciais: z.string(),
  conectadaEm: z.string(),
  ultimoSyncEm: z.string(),
});
export type ContaBancaria = z.infer<typeof contaBancariaSchema>;
export const contasBancariasSchema = z.array(contaBancariaSchema);

export const transacaoBancariaSchema = z.object({
  id: z.string(),
  contaId: z.string(),
  data: z.string(),
  descricao: z.string(),
  contraparte: z.string().optional(),
  valor: z.number(),
  tipo: tipoTransacaoSchema,
  categoria: categoriaTransacaoSchema,
  saldoApos: z.number(),
  conciliada: z.boolean().default(false),
  lancamentoId: z.string().optional(),
});
export type TransacaoBancaria = z.infer<typeof transacaoBancariaSchema>;
export const transacoesBancariasSchema = z.array(transacaoBancariaSchema);

export const tipoContaPagarReceberSchema = z.enum(["pagar", "receber"]);
export type TipoContaPagarReceber = z.infer<typeof tipoContaPagarReceberSchema>;

export const statusContaPagarReceberSchema = z.enum([
  "pendente",
  "pago",
  "atrasado",
]);
export type StatusContaPagarReceber = z.infer<
  typeof statusContaPagarReceberSchema
>;

export const categoriaContaSchema = z.enum([
  "fornecedor",
  "tributos",
  "folha",
  "aluguel",
  "energia",
  "telefonia_internet",
  "marketing",
  "servicos",
  "vendas",
  "servicos_prestados",
  "outros",
]);
export type CategoriaConta = z.infer<typeof categoriaContaSchema>;

export const CATEGORIA_CONTA_LABEL: Record<CategoriaConta, string> = {
  fornecedor: "Fornecedor",
  tributos: "Tributos",
  folha: "Folha",
  aluguel: "Aluguel",
  energia: "Energia",
  telefonia_internet: "Telefonia / internet",
  marketing: "Marketing",
  servicos: "Serviços contratados",
  vendas: "Vendas",
  servicos_prestados: "Serviços prestados",
  outros: "Outros",
};

export const contaPagarReceberSchema = z.object({
  id: z.string(),
  tipo: tipoContaPagarReceberSchema,
  descricao: z.string().min(3),
  contraparte: z.string().min(2),
  valor: z.number().positive(),
  vencimento: z.string(),
  categoria: categoriaContaSchema,
  status: statusContaPagarReceberSchema,
  pagoEm: z.string().optional(),
  observacao: z.string().optional(),
  criadoEm: z.string(),
});
export type ContaPagarReceber = z.infer<typeof contaPagarReceberSchema>;
export const contasPagarReceberSchema = z.array(contaPagarReceberSchema);

export const contaPagarReceberInputSchema = z.object({
  tipo: tipoContaPagarReceberSchema,
  descricao: z.string().min(3, "Descreva em pelo menos 3 letras"),
  contraparte: z.string().min(2, "Informe o contato"),
  valor: z.coerce.number().positive("Valor precisa ser maior que zero"),
  vencimento: z.string().min(10, "Informe a data de vencimento"),
  categoria: categoriaContaSchema,
  observacao: z.string().optional(),
});
export type ContaPagarReceberInput = z.infer<
  typeof contaPagarReceberInputSchema
>;

export const fluxoCaixaPontoSchema = z.object({
  data: z.string(),
  saldo: z.number(),
  entradas: z.number(),
  saidas: z.number(),
  projecao: z.boolean(),
});
export type FluxoCaixaPonto = z.infer<typeof fluxoCaixaPontoSchema>;

export const fluxoCaixaSchema = z.object({
  saldoHoje: z.number(),
  saldo30d: z.number(),
  saldo60d: z.number(),
  saldo90d: z.number(),
  diaSaldoNegativo: z.string().nullable(),
  pontos: z.array(fluxoCaixaPontoSchema),
});
export type FluxoCaixa = z.infer<typeof fluxoCaixaSchema>;
