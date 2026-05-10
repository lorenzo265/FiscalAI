import type { ContaContabil } from "@/lib/schemas/contabil";

// Plano de contas simplificado — alinhado com as principais contas usadas no Simples/Presumido.
// Códigos no padrão x.x.x.xx para hierarquia de 4 níveis.

export const PLANO_CONTAS: ContaContabil[] = [
  // === ATIVO ===
  { codigo: "1", pai: null, nome: "Ativo", natureza: "ativo", grupo: "ativo_circulante", analitica: false, nivel: 1 },
  { codigo: "1.1", pai: "1", nome: "Ativo Circulante", natureza: "ativo", grupo: "ativo_circulante", analitica: false, nivel: 2 },
  { codigo: "1.1.1", pai: "1.1", nome: "Disponibilidades", natureza: "ativo", grupo: "ativo_circulante", analitica: false, nivel: 3 },
  { codigo: "1.1.1.01", pai: "1.1.1", nome: "Caixa", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },
  { codigo: "1.1.1.02", pai: "1.1.1", nome: "Bancos · Conta Movimento", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },
  { codigo: "1.1.1.03", pai: "1.1.1", nome: "Aplicações Financeiras", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },

  { codigo: "1.1.2", pai: "1.1", nome: "Créditos a Receber", natureza: "ativo", grupo: "ativo_circulante", analitica: false, nivel: 3 },
  { codigo: "1.1.2.01", pai: "1.1.2", nome: "Clientes a Receber", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },
  { codigo: "1.1.2.02", pai: "1.1.2", nome: "Adiantamentos a Fornecedores", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },
  { codigo: "1.1.2.03", pai: "1.1.2", nome: "Tributos a Recuperar", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },

  { codigo: "1.1.3", pai: "1.1", nome: "Estoques", natureza: "ativo", grupo: "ativo_circulante", analitica: false, nivel: 3 },
  { codigo: "1.1.3.01", pai: "1.1.3", nome: "Mercadorias", natureza: "ativo", grupo: "ativo_circulante", analitica: true, nivel: 4 },

  { codigo: "1.2", pai: "1", nome: "Ativo Não Circulante", natureza: "ativo", grupo: "ativo_nao_circulante", analitica: false, nivel: 2 },
  { codigo: "1.2.1", pai: "1.2", nome: "Imobilizado", natureza: "ativo", grupo: "ativo_nao_circulante", analitica: false, nivel: 3 },
  { codigo: "1.2.1.01", pai: "1.2.1", nome: "Equipamentos de Informática", natureza: "ativo", grupo: "ativo_nao_circulante", analitica: true, nivel: 4 },
  { codigo: "1.2.1.02", pai: "1.2.1", nome: "Móveis e Utensílios", natureza: "ativo", grupo: "ativo_nao_circulante", analitica: true, nivel: 4 },
  { codigo: "1.2.1.99", pai: "1.2.1", nome: "(-) Depreciação Acumulada", natureza: "ativo", grupo: "ativo_nao_circulante", analitica: true, nivel: 4 },

  // === PASSIVO ===
  { codigo: "2", pai: null, nome: "Passivo", natureza: "passivo", grupo: "passivo_circulante", analitica: false, nivel: 1 },
  { codigo: "2.1", pai: "2", nome: "Passivo Circulante", natureza: "passivo", grupo: "passivo_circulante", analitica: false, nivel: 2 },
  { codigo: "2.1.1", pai: "2.1", nome: "Fornecedores", natureza: "passivo", grupo: "passivo_circulante", analitica: false, nivel: 3 },
  { codigo: "2.1.1.01", pai: "2.1.1", nome: "Fornecedores Nacionais", natureza: "passivo", grupo: "passivo_circulante", analitica: true, nivel: 4 },
  { codigo: "2.1.2", pai: "2.1", nome: "Tributos a Recolher", natureza: "passivo", grupo: "passivo_circulante", analitica: false, nivel: 3 },
  { codigo: "2.1.2.01", pai: "2.1.2", nome: "DAS Simples Nacional a Recolher", natureza: "passivo", grupo: "passivo_circulante", analitica: true, nivel: 4 },
  { codigo: "2.1.2.02", pai: "2.1.2", nome: "ISS a Recolher", natureza: "passivo", grupo: "passivo_circulante", analitica: true, nivel: 4 },
  { codigo: "2.1.2.03", pai: "2.1.2", nome: "INSS / FGTS a Recolher", natureza: "passivo", grupo: "passivo_circulante", analitica: true, nivel: 4 },
  { codigo: "2.1.3", pai: "2.1", nome: "Obrigações Trabalhistas", natureza: "passivo", grupo: "passivo_circulante", analitica: false, nivel: 3 },
  { codigo: "2.1.3.01", pai: "2.1.3", nome: "Salários a Pagar", natureza: "passivo", grupo: "passivo_circulante", analitica: true, nivel: 4 },

  // === PATRIMÔNIO LÍQUIDO ===
  { codigo: "3", pai: null, nome: "Patrimônio Líquido", natureza: "patrimonio_liquido", grupo: "patrimonio_liquido", analitica: false, nivel: 1 },
  { codigo: "3.1", pai: "3", nome: "Capital Social", natureza: "patrimonio_liquido", grupo: "patrimonio_liquido", analitica: false, nivel: 2 },
  { codigo: "3.1.1", pai: "3.1", nome: "Capital Subscrito", natureza: "patrimonio_liquido", grupo: "patrimonio_liquido", analitica: true, nivel: 3 },
  { codigo: "3.2", pai: "3", nome: "Resultado do Exercício", natureza: "patrimonio_liquido", grupo: "patrimonio_liquido", analitica: false, nivel: 2 },
  { codigo: "3.2.1", pai: "3.2", nome: "Lucros Acumulados", natureza: "patrimonio_liquido", grupo: "patrimonio_liquido", analitica: true, nivel: 3 },

  // === RECEITAS ===
  { codigo: "4", pai: null, nome: "Receitas", natureza: "receita", grupo: "receita_operacional", analitica: false, nivel: 1 },
  { codigo: "4.1", pai: "4", nome: "Receita Operacional", natureza: "receita", grupo: "receita_operacional", analitica: false, nivel: 2 },
  { codigo: "4.1.1", pai: "4.1", nome: "Receita de Serviços", natureza: "receita", grupo: "receita_operacional", analitica: true, nivel: 3 },
  { codigo: "4.1.2", pai: "4.1", nome: "Receita de Vendas", natureza: "receita", grupo: "receita_operacional", analitica: true, nivel: 3 },
  { codigo: "4.2", pai: "4", nome: "Receitas Financeiras", natureza: "receita", grupo: "receita_nao_operacional", analitica: true, nivel: 2 },

  // === DESPESAS ===
  { codigo: "5", pai: null, nome: "Despesas", natureza: "despesa", grupo: "despesa_operacional", analitica: false, nivel: 1 },
  { codigo: "5.1", pai: "5", nome: "Despesas Operacionais", natureza: "despesa", grupo: "despesa_operacional", analitica: false, nivel: 2 },
  { codigo: "5.1.1", pai: "5.1", nome: "Pessoal e Encargos", natureza: "despesa", grupo: "despesa_operacional", analitica: true, nivel: 3 },
  { codigo: "5.1.2", pai: "5.1", nome: "Aluguel e Condomínio", natureza: "despesa", grupo: "despesa_operacional", analitica: true, nivel: 3 },
  { codigo: "5.1.3", pai: "5.1", nome: "Serviços de Terceiros", natureza: "despesa", grupo: "despesa_operacional", analitica: true, nivel: 3 },
  { codigo: "5.1.4", pai: "5.1", nome: "Materiais e Insumos", natureza: "despesa", grupo: "despesa_operacional", analitica: true, nivel: 3 },
  { codigo: "5.1.5", pai: "5.1", nome: "Despesas Tributárias (DAS, etc.)", natureza: "despesa", grupo: "despesa_operacional", analitica: true, nivel: 3 },
  { codigo: "5.2", pai: "5", nome: "Despesas Financeiras", natureza: "despesa", grupo: "despesa_financeira", analitica: false, nivel: 2 },
  { codigo: "5.2.1", pai: "5.2", nome: "Tarifas e Juros Bancários", natureza: "despesa", grupo: "despesa_financeira", analitica: true, nivel: 3 },
];

export const CONTAS_POR_CODIGO = new Map(PLANO_CONTAS.map((c) => [c.codigo, c]));

export function buscarConta(codigo: string): ContaContabil | undefined {
  return CONTAS_POR_CODIGO.get(codigo);
}
