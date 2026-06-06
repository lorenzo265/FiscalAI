/**
 * Adapter de domínio: relatorios (Onda 2 / Fase E — integração com a API real).
 *
 * **Mudança-chave:** o cálculo dos relatórios saiu do cliente e foi para o
 * servidor. `dre`/`balanco`/`dfc`/`indicadores` agora chamam os endpoints reais
 * via `fetchJson` + `getEmpresaIdAtiva()`. A geração client-side
 * (`src/lib/relatorios/geracao.ts`) foi descartada — não é mais importada.
 *
 * Endpoints (descobertos por curl — ver handoff):
 *   - `POST /v1/empresas/{id}/relatorios/dre`         body `{periodo_inicio, periodo_fim}` (datas YYYY-MM-DD)
 *   - `POST /v1/empresas/{id}/relatorios/balanco`     body `{data_referencia}`
 *   - `POST /v1/empresas/{id}/relatorios/dfc`         body `{periodo_inicio, periodo_fim}`
 *   - `POST /v1/empresas/{id}/relatorios/indicadores` body `{periodo_inicio, periodo_fim}`
 *   - `GET  /v1/empresas/{id}/relatorios`             lista snapshots
 *
 * O envelope é `RelatorioOut` (`{id, empresa_id, tipo, periodo_*, payload, ...}`)
 * — `payload` é um dict estruturado, serializado pelo backend com TODO valor
 * monetário como **string decimal** (NUMERIC). O `fetchJson` cameliza a resposta
 * INTEIRA (inclusive as chaves dentro de `payload`), então aqui o payload chega
 * em camelCase (`receitaBruta`, `lucroLiquido`, …) com valores ainda string. A
 * conversão string→number acontece só na fronteira do mapper (os schemas Zod das
 * telas e a aritmética delas são `number`) — espelha o que o adapter fiscal faz.
 *
 * Divergência de SHAPE (servidor × telas) — resolvida por mapeamento, sem
 * inventar número:
 *   - **DRE:** o backend calcula UM período estruturado em cascata
 *     (ROB → deduções → … → lucro líquido). As telas esperam
 *     `{periodos[], linhas[]}` (formato comparativo multi-coluna). Mapeamos a
 *     cascata do backend para UMA coluna ("Mês atual"); as 3 margens são
 *     derivadas dos próprios valores do backend. A tabela e os cards de margem
 *     renderizam com 1 período sem quebrar.
 *   - **Indicadores:** o backend devolve 11 índices clássicos (Liquidez,
 *     Endividamento, Margens, ROA/ROE, Giro). As telas mostram cards com
 *     sparkline de 12 meses + tom/direção/variação. SEM série histórica no
 *     backend → série de 1 ponto (o próprio valor real); `direcao=estavel`,
 *     `variacao=0`; `tom` derivado de faixas determinísticas. Nada é fabricado.
 *
 * Estado vazio honesto: a empresa demo pode não ter lançamentos contábeis. Nesse
 * caso o backend responde `SemDadosContabeis` (HTTP 422). Tratamos como "sem
 * dados" — relatório vazio (zerado) — e as telas renderizam sem quebrar. NÃO
 * fabricamos valores.
 *
 * Dono na integração: agente de domínio relatorios.
 */
import { z } from "zod";

import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import {
  balancoPatrimonialSchema,
  dfcSchema,
  dreComparativoSchema,
  indicadoresSchema,
  type BalancoPatrimonial,
  type DFC,
  type DreComparativo,
  type Indicador,
  type LinhaBalanco,
  type LinhaDfc,
  type LinhaDre,
  type SparkPoint,
} from "@/lib/schemas/relatorios";

// ════════════════════════════════════════════════════════════════════════════
// Envelope + helpers de transporte
// ════════════════════════════════════════════════════════════════════════════

/**
 * Envelope `RelatorioOut`, já camelizado pelo `fetchJson`. `payload` é
 * estruturado e varia por tipo de relatório — validamos como dict aberto
 * (passthrough) aqui e tipamos cada payload no seu mapper. Valores monetários
 * dentro do payload são string decimal (preservados pelo `toCamel`).
 */
const relatorioOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipo: z.string(),
  periodoInicio: z.string(),
  periodoFim: z.string(),
  payload: z.record(z.string(), z.unknown()),
  algoritmoVersao: z.string(),
  supersededBy: z.string().nullable().optional(),
  criadoEm: z.string(),
});
type RelatorioOut = z.infer<typeof relatorioOutSchema>;

/** Linha do payload do backend: `{rotulo, valor(string), detalhes?[]}`. */
interface LinhaPayload {
  rotulo: string;
  valor: string | number | null;
  detalhes?: string[];
}

function dec(s: string | number | null | undefined): number {
  if (s == null) return 0;
  const n = typeof s === "number" ? s : Number(s);
  return Number.isFinite(n) ? n : 0;
}

/** Extrai `.valor` (string decimal) de uma linha-payload do backend → number. */
function valorLinha(l: unknown): number {
  if (l && typeof l === "object" && "valor" in l) {
    return dec((l as LinhaPayload).valor);
  }
  return 0;
}

function arredondar(n: number): number {
  return Math.round(n * 100) / 100;
}

function empresaIdOuErro(): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      400,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada."
    );
  }
  return id;
}

/** `true` quando o erro é "sem dados contábeis" (estado vazio honesto). */
function ehSemDados(err: unknown): boolean {
  return err instanceof ApiError && err.codigo === "SemDadosContabeis";
}

// ── Janela temporal (período corrente) ──────────────────────────────────────

const NOMES_MES_CURTO = [
  "jan", "fev", "mar", "abr", "mai", "jun",
  "jul", "ago", "set", "out", "nov", "dez",
];

function iso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dia}`;
}

/** Primeiro e último dia do mês de `hoje` (YYYY-MM-DD). */
function periodoMesCorrente(hoje = new Date()): {
  inicio: string;
  fim: string;
  competencia: string;
} {
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth(); // 0-based
  const inicio = new Date(ano, mes, 1);
  const fim = new Date(ano, mes + 1, 0); // dia 0 do mês seguinte = último dia
  const competencia = `${ano}-${String(mes + 1).padStart(2, "0")}`;
  return { inicio: iso(inicio), fim: iso(fim), competencia };
}

// ════════════════════════════════════════════════════════════════════════════
// Chamadas à API (POST gera/recupera o snapshot do período)
// ════════════════════════════════════════════════════════════════════════════

async function postRelatorio(
  sub: "dre" | "balanco" | "dfc" | "indicadores",
  body: Record<string, string>
): Promise<RelatorioOut> {
  const empresaId = empresaIdOuErro();
  return fetchJson(`/empresas/${empresaId}/relatorios/${sub}`, relatorioOutSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ════════════════════════════════════════════════════════════════════════════
// DRE — cascata do backend → formato comparativo das telas (1 coluna)
// ════════════════════════════════════════════════════════════════════════════

function dreVazio(competencia: string): DreComparativo {
  return dreComparativoSchema.parse({
    periodos: [{ ano: Number(competencia.slice(0, 4)), mes: Number(competencia.slice(5, 7)), rotulo: "Mês atual" }],
    linhas: [],
  });
}

function mapearDre(out: RelatorioOut, competencia: string): DreComparativo {
  const p = out.payload as Record<string, unknown>;
  const ano = Number(competencia.slice(0, 4));
  const mes = Number(competencia.slice(5, 7));

  const v = (chave: string): number => valorLinha(p[chave]);

  // Valores da cascata (já calculados pelo backend — não recalculamos).
  const receitaBruta = v("receitaBruta");
  const deducoes = v("deducoes");
  const receitaLiquida = v("receitaLiquida");
  const cmv = v("cmv");
  const lucroBruto = v("lucroBruto");
  const despesasPessoal = v("despesasPessoal");
  const outrasDespesas = v("outrasDespesas");
  const ebitda = v("ebitda");
  const depreciacao = v("depreciacao");
  const ebit = v("ebit");
  const outrasReceitas = v("outrasReceitas");
  const resultadoFinanceiro = v("resultadoFinanceiro");
  const lair = v("lair");
  const irpjCsll = v("irpjCsll");
  const lucroLiquido = v("lucroLiquido");

  const linhas: LinhaDre[] = [];
  const secao = (rotulo: string): void => {
    linhas.push({ chave: `secao-${rotulo}`, rotulo, tipo: "secao", valores: [0], formato: "moeda" });
  };
  const linha = (
    chave: string,
    rotulo: string,
    valor: number,
    tipo: LinhaDre["tipo"] = "linha"
  ): void => {
    linhas.push({ chave, rotulo, tipo, valores: [arredondar(valor)], formato: "moeda" });
  };

  secao("Receita");
  linha("receita-bruta", "Receita operacional bruta", receitaBruta, "subtotal");

  secao("Deduções");
  // Deduções e custos saem negativos na coluna (a tela colore como dedução).
  linha("deducoes", "Impostos sobre a receita", -deducoes, "deducao");
  linha("receita-liquida", "Receita líquida", receitaLiquida, "subtotal");

  secao("Custo");
  linha("cmv", "Custo de mercadorias / serviços (CMV/CSV)", -cmv, "deducao");
  linha("lucro-bruto", "Lucro bruto", lucroBruto, "subtotal");

  secao("Despesas operacionais");
  linha("desp-pessoal", "Pessoal e encargos", -despesasPessoal, "deducao");
  linha("outras-despesas", "Outras despesas operacionais", -outrasDespesas, "deducao");
  linha("ebitda", "EBITDA", ebitda, "subtotal");
  linha("depreciacao", "Depreciação / amortização", -depreciacao, "deducao");
  linha("ebit", "EBIT (resultado operacional)", ebit, "subtotal");

  secao("Resultado financeiro e não operacional");
  linha("outras-receitas", "Outras receitas", outrasReceitas);
  linha("resultado-financeiro", "Resultado financeiro", resultadoFinanceiro);
  linha("lair", "LAIR (lucro antes do IRPJ/CSLL)", lair, "subtotal");
  linha("irpj-csll", "IRPJ + CSLL", -irpjCsll, "deducao");
  linha("lucro-liquido", "Lucro líquido do período", lucroLiquido, "total");

  // ── Margens (derivadas dos valores do backend, base = ROB) ──
  const margem = (numerador: number): number =>
    receitaBruta > 0 ? arredondar((numerador / receitaBruta) * 100) : 0;
  linhas.push({
    chave: "margem-bruta",
    rotulo: "Margem bruta",
    tipo: "margem",
    formato: "percentual",
    valores: [margem(lucroBruto)],
  });
  linhas.push({
    chave: "margem-operacional",
    rotulo: "Margem operacional",
    tipo: "margem",
    formato: "percentual",
    valores: [margem(ebit)],
  });
  linhas.push({
    chave: "margem-liquida",
    rotulo: "Margem líquida",
    tipo: "margem",
    formato: "percentual",
    valores: [margem(lucroLiquido)],
  });

  return dreComparativoSchema.parse({
    periodos: [{ ano, mes, rotulo: "Mês atual" }],
    linhas,
  });
}

// ════════════════════════════════════════════════════════════════════════════
// Balanço — payload do backend → árvore plana de linhas das telas
// ════════════════════════════════════════════════════════════════════════════

function balancoVazio(competencia: string): BalancoPatrimonial {
  return balancoPatrimonialSchema.parse({
    competencia,
    ativo: [],
    passivoEPl: [],
    totalAtivo: 0,
    totalPassivo: 0,
    totalPl: 0,
    bate: true,
    diferenca: 0,
  });
}

/** Grupo do payload do balanço: `{rotulo, valor, contas: [[codigo, desc, saldo], …]}`. */
interface GrupoBalancoPayload {
  rotulo: string;
  valor: string | number | null;
  contas?: Array<[string, string, string | number]>;
}

function grupo(p: Record<string, unknown>, chave: string): GrupoBalancoPayload | null {
  const g = p[chave];
  if (g && typeof g === "object" && "valor" in g) return g as GrupoBalancoPayload;
  return null;
}

/** Empurra um grupo (linha "grupo") + suas contas (linha "conta") no destino. */
function empurrarGrupo(
  destino: LinhaBalanco[],
  g: GrupoBalancoPayload | null,
  codigoGrupo: string
): number {
  if (!g) return 0;
  const total = dec(g.valor);
  if (total === 0 && (!g.contas || g.contas.length === 0)) return 0;
  destino.push({
    codigo: codigoGrupo,
    rotulo: g.rotulo,
    valor: arredondar(total),
    destaque: "grupo",
    nivel: 1,
  });
  for (const c of g.contas ?? []) {
    const [codigo, desc, saldo] = c;
    if (dec(saldo) === 0) continue;
    destino.push({
      codigo,
      rotulo: desc,
      valor: arredondar(dec(saldo)),
      destaque: "conta",
      nivel: codigo.split(".").length,
    });
  }
  return total;
}

function mapearBalanco(out: RelatorioOut, competencia: string): BalancoPatrimonial {
  const p = out.payload as Record<string, unknown>;

  const ativoCirc = grupo(p, "ativoCirculante");
  const ativoNaoCirc = grupo(p, "ativoNaoCirculante");
  const passivoCirc = grupo(p, "passivoCirculante");
  const passivoNaoCirc = grupo(p, "passivoNaoCirculante");
  const pl = grupo(p, "patrimonioLiquido");

  const ativo: LinhaBalanco[] = [];
  empurrarGrupo(ativo, ativoCirc, "1.1");
  empurrarGrupo(ativo, ativoNaoCirc, "1.2");

  const passivoEPl: LinhaBalanco[] = [];
  const totPc = empurrarGrupo(passivoEPl, passivoCirc, "2.1");
  const totPnc = empurrarGrupo(passivoEPl, passivoNaoCirc, "2.2");
  const totPl = empurrarGrupo(passivoEPl, pl, "3");

  const totalAtivo = dec((grupo(p, "ativoTotal") ?? {}).valor);
  const totalPassivo = totPc + totPnc;

  // `fecha` / `diferenca` vêm do backend (invariante ATIVO = PASSIVO + PL).
  const bate = p["fecha"] === true;
  const diferenca = dec(p["diferenca"] as string | number | null);

  return balancoPatrimonialSchema.parse({
    competencia,
    ativo,
    passivoEPl,
    totalAtivo: arredondar(totalAtivo),
    totalPassivo: arredondar(totalPassivo),
    totalPl: arredondar(totPl),
    bate,
    diferenca: arredondar(diferenca),
  });
}

// ════════════════════════════════════════════════════════════════════════════
// DFC — cascata do backend → linhas seccionadas das telas
// ════════════════════════════════════════════════════════════════════════════

function dfcVazio(competencia: string): DFC {
  return dfcSchema.parse({
    competencia,
    saldoInicial: 0,
    saldoFinal: 0,
    linhas: [],
  });
}

function mapearDfc(out: RelatorioOut, competencia: string): DFC {
  const p = out.payload as Record<string, unknown>;
  const v = (chave: string): number => valorLinha(p[chave]);
  const linhas: LinhaDfc[] = [];

  const linha = (
    chave: string,
    rotulo: string,
    valor: number,
    tipo: LinhaDfc["tipo"] = "linha"
  ): void => {
    linhas.push({ chave, rotulo, tipo, valor: arredondar(valor) });
  };

  // ── Operacional ──
  linhas.push({ chave: "secao-op", rotulo: "Atividades operacionais", tipo: "secao", valor: 0 });
  linha("ll", "Lucro líquido do período", v("lucroLiquido"));
  linha("depreciacao", "(+) Depreciação / amortização", v("depreciacao"));
  linha("provisoes", "(+) Provisões constituídas", v("provisoes"));
  linha("var-clientes", "(−) Aumento de clientes", -v("variacaoClientes"));
  linha("var-estoques", "(−) Aumento de estoques", -v("variacaoEstoques"));
  linha("var-fornecedores", "(+) Aumento de fornecedores", v("variacaoFornecedores"));
  linha("var-encargos", "(+) Aumento de encargos a pagar", v("variacaoEncargos"));
  linha("total-op", "Caixa gerado pelas operações", v("caixaOperacional"), "subtotal");

  // ── Investimento ──
  linhas.push({ chave: "secao-inv", rotulo: "Atividades de investimento", tipo: "secao", valor: 0 });
  linha("inv-aquisicao", "(−) Aquisição de imobilizado", -v("aquisicaoImobilizado"));
  linha("inv-venda", "(+) Venda de imobilizado", v("vendaImobilizado"));
  linha("total-inv", "Caixa em investimentos", v("caixaInvestimento"), "subtotal");

  // ── Financiamento ──
  linhas.push({ chave: "secao-fin", rotulo: "Atividades de financiamento", tipo: "secao", valor: 0 });
  linha("fin-aporte", "(+) Aporte de capital", v("aporteCapital"));
  linha("fin-emprestimos", "(±) Empréstimos líquidos", v("emprestimosLiquidos"));
  linha("fin-distribuicao", "(−) Distribuição de lucros", -v("distribuicaoLucros"));
  linha("total-fin", "Caixa em financiamento", v("caixaFinanciamento"), "subtotal");

  linha("variacao-caixa", "Variação líquida de caixa", v("variacaoLiquidaCaixa"), "total");

  return dfcSchema.parse({
    competencia,
    saldoInicial: arredondar(v("saldoCaixaInicial")),
    saldoFinal: arredondar(v("saldoCaixaFinal")),
    linhas,
  });
}

// ════════════════════════════════════════════════════════════════════════════
// Indicadores — 11 índices do backend → cards das telas
// ════════════════════════════════════════════════════════════════════════════

/** Indicador-payload do backend: `{rotulo, valor(string|null), formato}`. */
interface IndicadorPayload {
  rotulo: string;
  valor: string | number | null;
  formato: string; // 'razao' | 'percentual'
}

function indPayload(p: Record<string, unknown>, chave: string): IndicadorPayload | null {
  const i = p[chave];
  if (i && typeof i === "object" && "valor" in i) return i as IndicadorPayload;
  return null;
}

/** Série de 1 ponto (valor real do período). NÃO fabricamos histórico. */
function serieUnica(valor: number): SparkPoint[] {
  return [{ rotulo: "atual", valor: arredondar(valor) }];
}

function mapearIndicadores(out: RelatorioOut): Indicador[] {
  const p = out.payload as Record<string, unknown>;
  const indicadores: Indicador[] = [];

  // backend dá Margens/Endividamento como razão (0..1) com formato 'percentual'
  // (caller multiplica × 100); Liquidez/Giro como razão pura. Convertemos no
  // ponto certo para casar com o `formato` das telas.
  const add = (
    chave: string,
    backendKey: string,
    titulo: string,
    descricao: string,
    formato: Indicador["formato"],
    tom: (v: number) => Indicador["tom"],
    percentual: boolean // true: valor backend × 100
  ): void => {
    const ip = indPayload(p, backendKey);
    if (!ip || ip.valor == null) return; // divisão por zero no backend → omite (N/A)
    const bruto = dec(ip.valor);
    const valor = arredondar(percentual ? bruto * 100 : bruto);
    indicadores.push({
      chave,
      titulo,
      descricao,
      valor,
      formato,
      tom: tom(valor),
      direcao: "estavel",
      variacao: 0,
      serie: serieUnica(valor),
    });
  };

  const tomLiquidez = (v: number): Indicador["tom"] =>
    v >= 1.5 ? "ok" : v >= 1 ? "warn" : "error";
  const tomEndiv = (v: number): Indicador["tom"] =>
    v <= 40 ? "ok" : v <= 65 ? "warn" : "error";
  const tomMargem = (v: number): Indicador["tom"] =>
    v >= 15 ? "ok" : v >= 5 ? "warn" : "error";
  const tomRetorno = (min: number) => (v: number): Indicador["tom"] =>
    v >= min ? "ok" : v >= 0 ? "warn" : "error";
  const tomNeutro = (): Indicador["tom"] => "neutral";

  add("liquidez-corrente", "liquidezCorrente", "Liquidez corrente",
    "Quanto a empresa tem a curto prazo para cada R$ 1 de obrigação",
    "decimal", tomLiquidez, false);
  add("liquidez-seca", "liquidezSeca", "Liquidez seca",
    "Liquidez sem depender da venda de estoques",
    "decimal", tomLiquidez, false);
  add("liquidez-geral", "liquidezGeral", "Liquidez geral",
    "Capacidade total de pagar dívidas de curto e longo prazo",
    "decimal", tomLiquidez, false);
  add("endividamento", "endividamentoGeral", "Endividamento",
    "Participação do capital de terceiros no total",
    "percentual", tomEndiv, true);
  add("composicao-endividamento", "composicaoEndividamento", "Composição do endividamento",
    "Quanto das dívidas vence no curto prazo",
    "percentual", tomNeutro, true);
  add("margem-bruta", "margemBruta", "Margem bruta",
    "Quanto sobra depois do custo direto, para cada R$ 100 vendidos",
    "percentual", tomMargem, true);
  add("margem-ebitda", "margemEbitda", "Margem EBITDA",
    "Geração de caixa operacional sobre a receita líquida",
    "percentual", tomMargem, true);
  add("margem-liquida", "margemLiquida", "Margem líquida",
    "Quanto sobra no fim para cada R$ 100 vendidos",
    "percentual", tomMargem, true);
  add("roa", "roa", "ROA",
    "Retorno sobre o ativo total",
    "percentual", tomRetorno(10), true);
  add("roe", "roe", "ROE",
    "Retorno sobre o patrimônio líquido",
    "percentual", tomRetorno(15), true);
  add("giro-ativo", "giroAtivo", "Giro do ativo",
    "Quantas vezes a receita cobre o ativo no período",
    "decimal", tomNeutro, false);

  return indicadoresSchema.parse(indicadores);
}

/** Traduz `ApiError.codigo` em mensagem amigável (nunca vaza código cru). */
export function mensagemAmigavelRelatorios(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível gerar o relatório agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "SemDadosContabeis":
      return "Ainda não há lançamentos contábeis suficientes para este relatório.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa ativa.";
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para ver os relatórios.";
    case "RelatorioNaoEncontrado":
      return "Relatório não encontrado.";
    default:
      return err.mensagem || "Não foi possível gerar o relatório agora.";
  }
}

// ════════════════════════════════════════════════════════════════════════════
// Superfície pública (assinaturas preservadas)
// ════════════════════════════════════════════════════════════════════════════

export const relatorios = {
  dre: async (): Promise<DreComparativo> => {
    const { inicio, fim, competencia } = periodoMesCorrente();
    try {
      const out = await postRelatorio("dre", {
        periodo_inicio: inicio,
        periodo_fim: fim,
      });
      return mapearDre(out, competencia);
    } catch (err) {
      if (ehSemDados(err)) return dreVazio(competencia);
      throw err;
    }
  },

  balanco: async (): Promise<BalancoPatrimonial> => {
    const { fim, competencia } = periodoMesCorrente();
    try {
      const out = await postRelatorio("balanco", { data_referencia: fim });
      return mapearBalanco(out, competencia);
    } catch (err) {
      if (ehSemDados(err)) return balancoVazio(competencia);
      throw err;
    }
  },

  dfc: async (): Promise<DFC> => {
    const { inicio, fim, competencia } = periodoMesCorrente();
    try {
      const out = await postRelatorio("dfc", {
        periodo_inicio: inicio,
        periodo_fim: fim,
      });
      return mapearDfc(out, competencia);
    } catch (err) {
      if (ehSemDados(err)) return dfcVazio(competencia);
      throw err;
    }
  },

  indicadores: async (): Promise<Indicador[]> => {
    const { inicio, fim } = periodoMesCorrente();
    try {
      const out = await postRelatorio("indicadores", {
        periodo_inicio: inicio,
        periodo_fim: fim,
      });
      return mapearIndicadores(out);
    } catch (err) {
      if (ehSemDados(err)) return [];
      throw err;
    }
  },
};
