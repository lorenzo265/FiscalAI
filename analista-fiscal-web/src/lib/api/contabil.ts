/**
 * Adapter de domínio: contábil (Onda 2 — integração front↔back).
 *
 * Fala com o backend FastAPI real via `fetchJson` (`@/lib/http`) +
 * `getEmpresaIdAtiva()`. Substitui o antigo Dexie/mock por leitura/escrita
 * reais do módulo contábil:
 *   - `GET  /v1/empresas/{id}/plano-contas`           → plano de contas vigente
 *   - `GET  /v1/empresas/{id}/lancamentos`            → lançamentos (com partidas)
 *   - `POST /v1/empresas/{id}/lancamentos`            → cria lançamento (rascunho)
 *   - `GET  /v1/empresas/{id}/contabil/balancete/{c}` → balancete por competência
 *
 * ──────────────────────────────────────────────────────────────────────────
 * Impedância de modelo (LEIA antes de mexer):
 *
 * O FRONT trabalha com um lançamento PLANO de partida dobrada simples
 * (`LancamentoContabil` = 1 conta débito + 1 conta crédito, por CÓDIGO de
 * conta `"1.1.1.02"`). O BACKEND usa N `partidas` (cada uma com `conta_id`
 * UUID + `tipo` 'D'/'C' + `valor`). A ponte entre os dois é o `codigo` da
 * conta (idêntico nos dois mundos — confirmado por curl: `1.1.1.02`, `5.1.06`).
 *
 * - Leitura: cada lançamento do backend é "explodido" em uma ou mais linhas
 *   planas do front, pareando partidas D × C (greedy por valor). O caso
 *   dominante (2 partidas: 1 D + 1 C) vira exatamente 1 linha. Partidas-dobradas
 *   preservadas — a soma dos `valor` das linhas geradas = total débito = total
 *   crédito do lançamento original.
 * - Escrita: o lançamento manual do front (1 D + 1 C, por código) é traduzido
 *   em 2 partidas com `conta_id` (UUID resolvido via plano) — o backend valida
 *   Σ débitos = Σ créditos.
 *
 * Dinheiro trafega como STRING decimal do backend; o schema Zod do front
 * (`LancamentoContabil.valor`) é `number` — convertemos na fronteira (só para
 * exibição/agregação no cliente; não é caminho de precisão monetária crítica).
 */
import { z } from "zod";

import { ApiError, fetchJson, toSnake } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import {
  lancamentoContabilSchema,
  type LancamentoContabil,
  type OrigemLancamento,
} from "@/lib/schemas/contabil";

// ── Schemas do backend (camelCase — `toCamel` roda no `fetchJson`) ───────────

/** Natureza da partida no backend: 'D' (débito) ou 'C' (crédito). */
const partidaNaturezaSchema = z.enum(["D", "C"]);

/** `tipo` (front-natureza) de uma conta do plano. */
const contaTipoSchema = z.enum([
  "ativo",
  "passivo",
  "patrimonio_liquido",
  "receita",
  "despesa",
  "conta_resultado",
]);

/** Conta do plano referencial (`ContaContabilOut`). */
const contaContabilBackendSchema = z.object({
  id: z.string(),
  codigo: z.string(),
  descricao: z.string(),
  parentId: z.string().nullable(),
  natureza: partidaNaturezaSchema,
  tipo: contaTipoSchema,
  nivel: z.number().int(),
  aceitaLancamento: z.boolean(),
  codigoEcdReferencial: z.string().nullable(),
  validFrom: z.string(),
  validTo: z.string().nullable(),
});
export type ContaContabilBackend = z.infer<typeof contaContabilBackendSchema>;

const planoContasSchema = z.array(contaContabilBackendSchema);

const partidaOutSchema = z.object({
  id: z.string(),
  contaContabilId: z.string(),
  tipo: partidaNaturezaSchema,
  valor: z.string(), // decimal string
  ordem: z.number().int(),
});

const origemTipoSchema = z.enum([
  "manual",
  "nfe",
  "transacao",
  "depreciacao",
  "provisao",
  "encerramento",
  "ajuste",
  "importacao",
  "folha",
]);

const statusLancamentoSchema = z.enum(["rascunho", "confirmado", "encerrado"]);

const lancamentoOutSchema = z.object({
  id: z.string(),
  dataLancamento: z.string(), // date YYYY-MM-DD
  competencia: z.string(),
  historico: z.string(),
  origemTipo: origemTipoSchema,
  origemId: z.string().nullable(),
  totalDebito: z.string(),
  totalCredito: z.string(),
  status: statusLancamentoSchema,
  criadoEm: z.string(),
  partidas: z.array(partidaOutSchema),
});
export type LancamentoOutBackend = z.infer<typeof lancamentoOutSchema>;
const lancamentosOutSchema = z.array(lancamentoOutSchema);

// ── Balancete (exposto para uso futuro; telas hoje calculam no cliente) ──────

const linhaBalanceteSchema = z.object({
  contaId: z.string(),
  codigo: z.string(),
  descricao: z.string(),
  natureza: partidaNaturezaSchema,
  tipo: contaTipoSchema,
  nivel: z.number().int(),
  saldoInicial: z.string(),
  totalDebitos: z.string(),
  totalCreditos: z.string(),
  saldoFinal: z.string(),
});
export type LinhaBalanceteBackend = z.infer<typeof linhaBalanceteSchema>;

const balanceteSchema = z.object({
  competencia: z.string(),
  linhas: z.array(linhaBalanceteSchema),
  totalDebitos: z.string(),
  totalCreditos: z.string(),
});
export type BalanceteBackend = z.infer<typeof balanceteSchema>;

// ── Mapeamentos de enum ──────────────────────────────────────────────────────

/**
 * `origem_tipo` do backend → `origem` do front. O front tem rótulos mais
 * granulares (nf_saida/nf_entrada/bancario/folha) que o backend não distingue
 * (`nfe`/`transacao`). Mapeamos para o rótulo mais próximo SEM inventar dado:
 *   - nfe        → nf_saida   (entrada vs saída não é exposto aqui)
 *   - transacao  → bancario
 *   - folha      → folha       (lançamento automático do fechamento da folha)
 *   - provisao   → folha       (provisões trabalhistas — o front agrupa em "folha")
 *   - depreciacao→ fiscal
 *   - encerramento→ encerramento
 *   - ajuste     → manual
 *   - manual     → manual
 */
function mapearOrigem(origemTipo: LancamentoOutBackend["origemTipo"]): OrigemLancamento {
  switch (origemTipo) {
    case "nfe":
      return "nf_saida";
    case "transacao":
      return "bancario";
    case "folha":
    case "provisao":
      return "folha";
    case "depreciacao":
      return "fiscal";
    case "encerramento":
      return "encerramento";
    case "ajuste":
    case "manual":
    default:
      return "manual";
  }
}

/** Front-origem → backend `origem_tipo` (apenas o que a escrita manual usa). */
function mapearOrigemParaBackend(origem: OrigemLancamento): string {
  // O único caminho de escrita do front é o lançamento manual; mantemos o mapa
  // conservador (o backend valida o enum).
  switch (origem) {
    case "manual":
      return "manual";
    case "nf_saida":
    case "nf_entrada":
      return "nfe";
    case "bancario":
      return "transacao";
    case "folha":
      return "provisao";
    case "fiscal":
      return "ajuste";
    case "encerramento":
      return "encerramento";
    default:
      return "manual";
  }
}

// ── Tradução conta UUID ⇄ código ─────────────────────────────────────────────

type PlanoIndex = {
  porId: Map<string, string>; // conta_id → codigo
  porCodigo: Map<string, string>; // codigo → conta_id
};

async function carregarPlanoIndex(empresaId: string): Promise<PlanoIndex> {
  const contas = await fetchJson(
    `/empresas/${empresaId}/plano-contas`,
    planoContasSchema
  );
  const porId = new Map<string, string>();
  const porCodigo = new Map<string, string>();
  for (const c of contas) {
    porId.set(c.id, c.codigo);
    porCodigo.set(c.codigo, c.id);
  }
  return { porId, porCodigo };
}

// ── Explosão de partidas → linhas planas do front ────────────────────────────

/**
 * Converte um lançamento do backend (N partidas, contas por UUID) em uma ou
 * mais linhas planas do front (1 D + 1 C, contas por código). Pareia partidas
 * de débito contra partidas de crédito por valor (greedy), preservando
 * Σ débitos = Σ créditos. O caso dominante (1 D + 1 C) gera exatamente 1 linha.
 */
function explodirLancamento(
  lanc: LancamentoOutBackend,
  porId: Map<string, string>
): LancamentoContabil[] {
  const codigoDe = (contaId: string): string => porId.get(contaId) ?? contaId;

  const debitos = lanc.partidas
    .filter((p) => p.tipo === "D")
    .map((p) => ({ conta: codigoDe(p.contaContabilId), restante: Number(p.valor) }));
  const creditos = lanc.partidas
    .filter((p) => p.tipo === "C")
    .map((p) => ({ conta: codigoDe(p.contaContabilId), restante: Number(p.valor) }));

  const origem = mapearOrigem(lanc.origemTipo);
  const base = {
    data: lanc.dataLancamento,
    historico: lanc.historico,
    origem,
    origemRefId: lanc.origemId ?? undefined,
    confianca: 1,
    criadoEm: lanc.criadoEm,
  };

  // Caso simples e dominante: 1 D + 1 C → 1 linha, sem heurística.
  if (debitos.length === 1 && creditos.length === 1) {
    return [
      {
        ...base,
        id: lanc.id,
        contaDebito: debitos[0]!.conta,
        contaCredito: creditos[0]!.conta,
        valor: Number(lanc.totalDebito),
      },
    ];
  }

  // Caso N partidas: pareia D × C por valor, gerando sub-linhas estáveis.
  const linhas: LancamentoContabil[] = [];
  let i = 0;
  let j = 0;
  let seq = 0;
  const EPS = 0.005;
  while (i < debitos.length && j < creditos.length) {
    const d = debitos[i]!;
    const c = creditos[j]!;
    const valor = Math.min(d.restante, c.restante);
    if (valor > EPS) {
      linhas.push({
        ...base,
        id: `${lanc.id}:${seq}`,
        contaDebito: d.conta,
        contaCredito: c.conta,
        valor: Number(valor.toFixed(2)),
      });
      seq += 1;
    }
    d.restante -= valor;
    c.restante -= valor;
    if (d.restante <= EPS) i += 1;
    if (c.restante <= EPS) j += 1;
  }

  // Fallback defensivo: lançamento sem par D/C utilizável → 1 linha honesta.
  if (linhas.length === 0) {
    return [
      {
        ...base,
        id: lanc.id,
        contaDebito: debitos[0]?.conta ?? "",
        contaCredito: creditos[0]?.conta ?? "",
        valor: Number(lanc.totalDebito),
      },
    ];
  }
  return linhas;
}

// ── API pública do domínio ───────────────────────────────────────────────────

function empresaIdObrigatoria(): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      400,
      "EmpresaNaoSelecionada",
      "Selecione uma empresa para ver a contabilidade."
    );
  }
  return id;
}

/**
 * Lista os lançamentos contábeis da empresa ativa, no formato plano que as
 * telas (Livro Diário, Balancete, Razão) consomem via `listarLancamentos`.
 * Ordenado por data ascendente (preserva a forma do antigo db-service).
 */
export async function listarLancamentos(): Promise<LancamentoContabil[]> {
  const empresaId = getEmpresaIdAtiva();
  if (!empresaId) return [];

  const [lancamentos, plano] = await Promise.all([
    fetchJson(`/empresas/${empresaId}/lancamentos`, lancamentosOutSchema),
    carregarPlanoIndex(empresaId),
  ]);

  const linhas = lancamentos.flatMap((l) => explodirLancamento(l, plano.porId));
  // Valida cada linha contra o schema do front (mesma garantia do mock).
  const validadas = linhas.map((l) => lancamentoContabilSchema.parse(l));
  return validadas.sort((a, b) => a.data.localeCompare(b.data));
}

/**
 * Cria um lançamento manual (1 débito + 1 crédito, contas por código). Resolve
 * os códigos para `conta_id` via o plano vigente e posta as 2 partidas. O
 * backend cria em status `rascunho` (a tela não distingue rascunho/confirmado).
 */
export async function adicionarLancamento(
  lancamento: LancamentoContabil
): Promise<void> {
  const empresaId = empresaIdObrigatoria();
  const plano = await carregarPlanoIndex(empresaId);

  const contaDebitoId = plano.porCodigo.get(lancamento.contaDebito);
  const contaCreditoId = plano.porCodigo.get(lancamento.contaCredito);
  if (!contaDebitoId || !contaCreditoId) {
    throw new ApiError(
      422,
      "ContaInexistente",
      "Conta de débito ou crédito não existe no plano de contas vigente."
    );
  }

  const valorStr = lancamento.valor.toFixed(2);
  const dataLanc = lancamento.data.slice(0, 10);
  // Competência = primeiro dia do mês do lançamento (backend espera date).
  const competencia = `${dataLanc.slice(0, 7)}-01`;

  const body = {
    dataLancamento: dataLanc,
    competencia,
    historico: lancamento.historico,
    partidas: [
      { contaId: contaDebitoId, tipo: "D", valor: valorStr },
      { contaId: contaCreditoId, tipo: "C", valor: valorStr },
    ],
  };

  await fetchJson(`/empresas/${empresaId}/lancamentos`, lancamentoOutSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toSnake(body)),
  });
}

/**
 * Remoção de lançamento. ⚠️ O backend NÃO expõe DELETE de lançamento (fatos
 * contábeis são imutáveis — princípio §8.2). Mantemos a assinatura para o hook,
 * mas a operação não está disponível pela API real. Nenhuma tela aciona isto.
 */
export async function removerLancamento(_id: string): Promise<void> {
  throw new ApiError(
    405,
    "OperacaoNaoSuportada",
    "Lançamentos contábeis não podem ser excluídos (fatos imutáveis)."
  );
}

/** Balancete de verificação por competência (`YYYY-MM`). Exposto para uso futuro. */
export async function obterBalancete(
  competencia: string
): Promise<BalanceteBackend> {
  const empresaId = empresaIdObrigatoria();
  return fetchJson(
    `/empresas/${empresaId}/contabil/balancete/${competencia}`,
    balanceteSchema
  );
}

/** Plano de contas vigente (lista de contas do backend). */
export async function listarPlanoContas(): Promise<ContaContabilBackend[]> {
  const empresaId = empresaIdObrigatoria();
  return fetchJson(`/empresas/${empresaId}/plano-contas`, planoContasSchema);
}

/** Traduz `ApiError.codigo` do domínio contábil em mensagem amigável. */
export function mensagemAmigavelContabil(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível carregar a contabilidade agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para ver a contabilidade.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa ativa.";
    case "ContaInexistente":
      return "Conta de débito ou crédito não existe no plano de contas vigente.";
    case "LancamentoInvalido":
    case "LancamentoDesbalanceado":
    case "PartidasDobradasInvalidas":
      return "O lançamento não fecha: o total de débitos deve igualar o de créditos.";
    case "ContaNaoAnalitica":
      return "Só é possível lançar em contas analíticas (de último nível).";
    case "CompetenciaEncerrada":
      return "Este mês já foi encerrado — não aceita novos lançamentos.";
    case "OperacaoNaoSuportada":
      return "Lançamentos contábeis não podem ser excluídos (fatos imutáveis).";
    case "PlanoContasVazio":
      return "Plano de contas ainda não foi configurado para esta empresa.";
    default:
      return err.mensagem || "Não foi possível concluir a operação contábil.";
  }
}

/**
 * Superfície `api.contabil` exposta no barrel. Mantém a leitura de lançamentos
 * como cidadã de primeira classe (relatórios também a consome via
 * `listarLancamentos`).
 */
export const contabil = {
  listarLancamentos,
  adicionarLancamento,
  removerLancamento,
  obterBalancete,
  listarPlanoContas,
  mensagemAmigavel: mensagemAmigavelContabil,
} as const;
