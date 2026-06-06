/**
 * Camada de dados de Controles (tesouraria) — Onda 2 / Fase E.
 *
 * O que vem do BACKEND REAL (Open Finance / Pluggy, via `fetchJson` +
 * `getEmpresaIdAtiva()`):
 *   - Contas bancárias conectadas → `GET /v1/empresas/{id}/contas-bancarias`.
 *   - Transações bancárias        → `GET /v1/empresas/{id}/transacoes`.
 *   - Sincronização manual        → `POST …/open-finance/items/{item_uuid}/sync`.
 *
 * O que NÃO TEM endpoint e por isso permanece LOCAL (Dexie/cliente), de forma
 * explícita — nada é fingido como vindo do backend (ver `hadoff-front-back.md`):
 *   - **Conectar conta** por clique no grid de bancos: o fluxo real exige o
 *     widget Pluggy (connect-token → widget → registrar item → sync). Sem o
 *     widget no protótipo, `conectarNovaConta` grava uma conta LOCAL no Dexie.
 *   - **Conciliação banco × lançamento contábil**: o front liga uma transação a
 *     um `LancamentoContabil` (Livro Diário). O backend tem conciliação NF × banco
 *     (entidade `Match`, semântica diferente) — NÃO há vínculo transação↔lançamento.
 *     O estado de conciliação é persistido LOCALMENTE (Dexie p/ tx local,
 *     `localStorage` p/ tx do backend).
 *   - **Contas a pagar / receber** e **fluxo de caixa**: sem endpoint → 100% Dexie
 *     / cálculo cliente (fluxo derivado das contas/transações reais quando houver).
 *
 * Dinheiro trafega como string decimal (NUMERIC) e só vira `number` na fronteira
 * do mapper (os schemas Zod das telas e a aritmética delas são `number`).
 *
 * Dono na integração: agente de domínio controles.
 */
import { z } from "zod";

import { getDb } from "@/lib/db";
import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  CategoriaTransacao,
  ContaBancaria,
  ContaPagarReceber,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import {
  gerarContasIniciais,
  gerarContasPagarReceberIniciais,
  gerarTransacoesIniciais,
} from "@/lib/mocks/controles";
import {
  BANCOS_OPENFINANCE,
  type BancoOpenFinance,
} from "@/lib/mocks/seeds/bancos-openfinance";
import { pseudoUuid } from "@/lib/mocks/utils";

const SEED_KEY = "analista-fiscal:controles-seeded";

// ── Shapes REAIS do backend (camelizados pelo fetchJson) ─────────────────────
// `ContaBancariaOut` (open-finance). Dinheiro = string decimal.
const contaBancariaOutSchema = z.object({
  id: z.string(),
  pluggyItemId: z.string(),
  pluggyAccountId: z.string(),
  bancoNome: z.string().nullable(),
  agencia: z.string().nullable(),
  numero: z.string().nullable(),
  tipo: z.string(), // CHECKING | SAVINGS | CREDIT_CARD
  subtipo: z.string().nullable(),
  moeda: z.string(),
  saldoAtual: z.string(),
  saldoDisponivel: z.string().nullable(),
  saldoAtualizadoEm: z.string().nullable(),
});
const contasBancariasOutSchema = z.array(contaBancariaOutSchema);

// `TransacaoBancariaOut` (open-finance).
const transacaoBancariaOutSchema = z.object({
  id: z.string(),
  contaBancariaId: z.string(),
  pluggyTransactionId: z.string(),
  dataTransacao: z.string(), // "YYYY-MM-DD"
  valor: z.string(), // decimal; sinal indica crédito/débito
  descricao: z.string().nullable(),
  tipo: z.string(), // CREDIT | DEBIT
  status: z.string(), // PENDING | CONFIRMED
  categoriaPluggy: z.string().nullable(),
  merchantCnpj: z.string().nullable(),
  merchantNome: z.string().nullable(),
});
const transacoesBancariasOutSchema = z.array(transacaoBancariaOutSchema);

type ContaBancariaOut = z.infer<typeof contaBancariaOutSchema>;
type TransacaoBancariaOut = z.infer<typeof transacaoBancariaOutSchema>;

// ── Helpers ──────────────────────────────────────────────────────────────────
function dec(s: string | null | undefined): number {
  if (s == null) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

/** Deriva a identidade visual (cor/iniciais) do banco a partir do nome cru. */
function bancoPorNome(nome: string | null): BancoOpenFinance {
  const alvo = (nome ?? "").toLowerCase();
  const achado = BANCOS_OPENFINANCE.find(
    (b) =>
      alvo.includes(b.nome.toLowerCase()) ||
      alvo.includes(b.id.toLowerCase()) ||
      alvo.includes(b.apelido.toLowerCase())
  );
  if (achado) return achado;
  // Banco desconhecido: identidade neutra (sem inventar marca).
  const iniciais = (nome ?? "Banco").trim().slice(0, 3).toUpperCase() || "BCO";
  return {
    id: `outro:${alvo || "banco"}`,
    nome: nome ?? "Banco",
    apelido: nome ?? "Conta bancária",
    cor: "#1f2937",
    textoCor: "#ffffff",
    iniciais,
  };
}

/**
 * Mapeia `categoria_pluggy` (string livre da Pluggy) para a taxonomia fechada da
 * tela. Heurística conservadora; o que não casa cai em "outros" (NÃO inventamos
 * uma categoria fiscal específica). `tipo` (CREDIT/DEBIT) refina o fallback.
 */
function mapearCategoria(
  categoriaPluggy: string | null,
  credito: boolean
): CategoriaTransacao {
  const c = (categoriaPluggy ?? "").toLowerCase();
  if (/(payroll|salar|folha)/.test(c)) return "folha_pagamento";
  if (/(tax|tribut|imposto|das|iss)/.test(c)) return "tributos";
  if (/(fee|tarifa|juros|bank)/.test(c)) return "tarifas_bancarias";
  if (/(transfer|ted|pix|doc)/.test(c)) return "transferencia";
  if (/(refund|estorno)/.test(c)) return "estorno";
  if (/(yield|rendiment|invest)/.test(c)) return "rendimento";
  if (/(supplier|fornecedor|compra)/.test(c)) return "pagamento_fornecedor";
  if (/(sale|venda|receit)/.test(c)) return "receita_vendas";
  // Sem categoria reconhecível → fallback pela direção do dinheiro.
  if (credito) return "recebimento_cliente";
  return "outros";
}

// ── Estado de conciliação LOCAL (sem endpoint no backend) ────────────────────
// O backend não modela "transação bancária ↔ lançamento contábil". Persistimos
// o vínculo localmente: tx do backend em localStorage (por empresa); tx local
// fica no próprio registro Dexie.
const CONCIL_KEY = "arkan:controles-conciliacao";

type ConcilMap = Record<string, string | null>; // txId → lancamentoId | null

function lerConcilMap(): ConcilMap {
  if (typeof window === "undefined") return {};
  const eid = getEmpresaIdAtiva() ?? "_";
  try {
    const raw = localStorage.getItem(`${CONCIL_KEY}:${eid}`);
    return raw ? (JSON.parse(raw) as ConcilMap) : {};
  } catch {
    return {};
  }
}

function gravarConcil(txId: string, lancamentoId: string | null): void {
  if (typeof window === "undefined") return;
  const eid = getEmpresaIdAtiva() ?? "_";
  const mapa = lerConcilMap();
  if (lancamentoId == null) {
    delete mapa[txId];
  } else {
    mapa[txId] = lancamentoId;
  }
  localStorage.setItem(`${CONCIL_KEY}:${eid}`, JSON.stringify(mapa));
}

// ── Mapeadores backend → schema da tela ──────────────────────────────────────
function mapearConta(out: ContaBancariaOut): ContaBancaria {
  const banco = bancoPorNome(out.bancoNome);
  return {
    id: out.id,
    bancoId: banco.id,
    bancoNome: out.bancoNome ?? banco.nome,
    apelido: out.bancoNome
      ? `${out.bancoNome} · Conta`
      : `${banco.nome} · Conta`,
    agencia: out.agencia ?? "—",
    numero: out.numero ?? "—",
    saldo: dec(out.saldoAtual),
    cor: banco.cor,
    textoCor: banco.textoCor,
    iniciais: banco.iniciais,
    conectadaEm: out.saldoAtualizadoEm ?? new Date().toISOString(),
    ultimoSyncEm: out.saldoAtualizadoEm ?? new Date().toISOString(),
  };
}

function mapearTransacao(
  out: TransacaoBancariaOut,
  concil: ConcilMap
): TransacaoBancaria {
  const credito = out.tipo.toUpperCase() === "CREDIT";
  const lancamentoId = concil[out.id] ?? undefined;
  return {
    id: out.id,
    contaId: out.contaBancariaId,
    data: out.dataTransacao,
    descricao: out.descricao ?? (credito ? "Crédito" : "Débito"),
    contraparte: out.merchantNome ?? undefined,
    // valor SEMPRE positivo no schema da tela; o sinal vira `tipo`.
    valor: Math.abs(dec(out.valor)),
    tipo: credito ? "credito" : "debito",
    categoria: mapearCategoria(out.categoriaPluggy, credito),
    // Backend não fornece saldo corrido por transação → 0 (a tela de extrato
    // não usa `saldoApos`; o schema exige number). NÃO inventamos um saldo.
    saldoApos: 0,
    conciliada: lancamentoId != null,
    lancamentoId,
  };
}

// ── Distinção conta real (backend) × conta local (Dexie) ─────────────────────
// IDs do backend são UUID; contas locais usam o prefixo `conta-`.
function isContaLocal(id: string): boolean {
  return id.startsWith("conta-");
}

async function contasBackend(): Promise<ContaBancaria[]> {
  const empresaId = getEmpresaIdAtiva();
  if (!empresaId) return [];
  try {
    const out = await fetchJson(
      `/empresas/${empresaId}/contas-bancarias`,
      contasBancariasOutSchema
    );
    return out.map(mapearConta);
  } catch (err) {
    // Sem Open Finance conectado / indisponível → lista vazia honesta.
    if (err instanceof ApiError) return [];
    throw err;
  }
}

async function contasLocais(): Promise<ContaBancaria[]> {
  const db = getDb();
  const lista = await db.contasBancarias.toArray();
  return lista.filter((c) => isContaLocal(c.id));
}

// ── Seed: só popula contas/transações LOCAIS de demonstração (Dexie) ─────────
// Mantido para a experiência do protótipo enquanto não há contas reais Pluggy.
export async function garantirSeedControles(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;

  const db = getDb();
  const totalContas = await db.contasBancarias.count();
  if (totalContas === 0) {
    const contas = gerarContasIniciais(empresa);
    await db.contasBancarias.bulkPut(contas);
    const transacoes = contas.flatMap((c) => gerarTransacoesIniciais(c, 60));
    await db.transacoes.bulkPut(transacoes);
  }

  const totalCpr = await db.contasPagarReceber.count();
  if (totalCpr === 0) {
    await db.contasPagarReceber.bulkPut(
      gerarContasPagarReceberIniciais(empresa)
    );
  }

  localStorage.setItem(flag, "1");
}

// ── Contas bancárias (REAL + local) ──────────────────────────────────────────
export async function listarContasBancarias(): Promise<ContaBancaria[]> {
  const [reais, locais] = await Promise.all([contasBackend(), contasLocais()]);
  const lista = [...reais, ...locais];
  return lista.sort((a, b) => a.conectadaEm.localeCompare(b.conectadaEm));
}

export async function obterContaBancaria(
  id: string
): Promise<ContaBancaria | undefined> {
  if (isContaLocal(id)) {
    const db = getDb();
    return db.contasBancarias.get(id);
  }
  const reais = await contasBackend();
  return reais.find((c) => c.id === id);
}

/**
 * Sincroniza a conta.
 *  - Conta REAL (backend): dispara `POST …/open-finance/items/{pluggy_item_id}/sync`
 *    e relê a conta atualizada do backend.
 *  - Conta LOCAL (Dexie): mantém o comportamento de demonstração (mexe no saldo
 *    sintético) — explicitamente local.
 */
export async function sincronizarConta(
  id: string
): Promise<ContaBancaria | undefined> {
  if (isContaLocal(id)) {
    const db = getDb();
    const conta = await db.contasBancarias.get(id);
    if (!conta) return undefined;
    const variacao = (Math.random() * 0.06 - 0.02) * conta.saldo;
    const novoSaldo = Math.round((conta.saldo + variacao) * 100) / 100;
    const atualizada: ContaBancaria = {
      ...conta,
      saldo: novoSaldo,
      ultimoSyncEm: new Date().toISOString(),
    };
    await db.contasBancarias.put(atualizada);
    return atualizada;
  }

  const empresaId = getEmpresaIdAtiva();
  if (!empresaId) return undefined;

  // Precisamos do `pluggy_item_id` (UUID do item) para a rota de sync. Ele vem
  // no `ContaBancariaOut.pluggyItemId`. Buscamos o shape cru novamente.
  const out = await fetchJson(
    `/empresas/${empresaId}/contas-bancarias`,
    contasBancariasOutSchema
  );
  const alvo = out.find((c) => c.id === id);
  if (!alvo) return undefined;

  try {
    await fetchJson(
      `/empresas/${empresaId}/open-finance/items/${alvo.pluggyItemId}/sync`,
      z.object({
        contasProcessadas: z.number(),
        contasNovas: z.number(),
        transacoesProcessadas: z.number(),
      }),
      { method: "POST" }
    );
  } catch (err) {
    // Sync indisponível (Pluggy off no ambiente) → devolve a conta como está,
    // sem fabricar saldo.
    if (!(err instanceof ApiError)) throw err;
  }

  const atualizado = await fetchJson(
    `/empresas/${empresaId}/contas-bancarias`,
    contasBancariasOutSchema
  );
  const conta = atualizado.find((c) => c.id === id);
  return conta ? mapearConta(conta) : undefined;
}

/**
 * GAP CONHECIDO: conectar conta por clique exige o widget Pluggy (não há no
 * protótipo). Mantida LOCAL (Dexie) — conta de demonstração, explicitamente não
 * vinda do backend. Quando o widget existir: connect-token → widget → POST
 * `/open-finance/items` → sync.
 */
export async function conectarNovaConta(
  empresa: Empresa,
  bancoId: string
): Promise<ContaBancaria> {
  const banco =
    BANCOS_OPENFINANCE.find((b) => b.id === bancoId) ?? BANCOS_OPENFINANCE[0]!;
  const db = getDb();
  const id = `conta-${empresa.id}-${bancoId}-${pseudoUuid().slice(0, 6)}`;
  const saldo = Math.round((8_000 + Math.random() * 90_000) * 100) / 100;
  const conta: ContaBancaria = {
    id,
    bancoId: banco.id,
    bancoNome: banco.nome,
    apelido: `${banco.nome} · Conta principal`,
    agencia: String(1000 + Math.floor(Math.random() * 8999)).padStart(4, "0"),
    numero: `${10000 + Math.floor(Math.random() * 89999)}-${Math.floor(Math.random() * 9)}`,
    saldo,
    cor: banco.cor,
    textoCor: banco.textoCor,
    iniciais: banco.iniciais,
    conectadaEm: new Date().toISOString(),
    ultimoSyncEm: new Date().toISOString(),
  };
  await db.contasBancarias.put(conta);
  const transacoes = gerarTransacoesIniciais(conta, 30);
  await db.transacoes.bulkPut(transacoes);
  return conta;
}

// ── Transações (REAL + local), com overlay de conciliação local ──────────────
async function transacoesBackend(contaId?: string): Promise<TransacaoBancaria[]> {
  const empresaId = getEmpresaIdAtiva();
  if (!empresaId) return [];
  const qs = new URLSearchParams({ limite: "1000" });
  if (contaId && !isContaLocal(contaId)) qs.set("conta_id", contaId);
  try {
    const out = await fetchJson(
      `/empresas/${empresaId}/transacoes?${qs.toString()}`,
      transacoesBancariasOutSchema
    );
    const concil = lerConcilMap();
    return out.map((t) => mapearTransacao(t, concil));
  } catch (err) {
    if (err instanceof ApiError) return [];
    throw err;
  }
}

export async function listarTransacoes(
  contaId: string
): Promise<TransacaoBancaria[]> {
  let lista: TransacaoBancaria[];
  if (isContaLocal(contaId)) {
    const db = getDb();
    lista = await db.transacoes.where("contaId").equals(contaId).toArray();
  } else {
    lista = await transacoesBackend(contaId);
  }
  return lista.sort((a, b) => b.data.localeCompare(a.data));
}

export async function listarTodasTransacoes(): Promise<TransacaoBancaria[]> {
  const db = getDb();
  const locais = (await db.transacoes.toArray()).filter((t) =>
    isContaLocal(t.contaId)
  );
  const reais = await transacoesBackend();
  const lista = [...reais, ...locais];
  return lista.sort((a, b) => b.data.localeCompare(a.data));
}

/**
 * Vincula/desvincula uma transação a um lançamento contábil.
 * GAP: não há endpoint para esse vínculo (a conciliação do backend é NF×banco,
 * não transação×lançamento). Persistência LOCAL: Dexie p/ tx local, localStorage
 * p/ tx do backend.
 */
export async function conciliarTransacao(
  transacaoId: string,
  lancamentoId: string | null
): Promise<void> {
  const db = getDb();
  const tx = await db.transacoes.get(transacaoId);
  if (tx) {
    // Transação local (Dexie).
    await db.transacoes.put({
      ...tx,
      conciliada: lancamentoId != null,
      lancamentoId: lancamentoId ?? undefined,
    });
    return;
  }
  // Transação do backend: persiste o vínculo no overlay local.
  gravarConcil(transacaoId, lancamentoId);
}

// ── Contas a pagar/receber (LOCAL — sem endpoint no backend) ─────────────────
export async function listarContasPagarReceber(): Promise<ContaPagarReceber[]> {
  const db = getDb();
  const lista = await db.contasPagarReceber.toArray();
  return lista.sort((a, b) => a.vencimento.localeCompare(b.vencimento));
}

export async function adicionarContaPagarReceber(
  conta: ContaPagarReceber
): Promise<void> {
  const db = getDb();
  await db.contasPagarReceber.put(conta);
}

export async function atualizarContaPagarReceber(
  conta: ContaPagarReceber
): Promise<void> {
  const db = getDb();
  await db.contasPagarReceber.put(conta);
}

export async function removerContaPagarReceber(id: string): Promise<void> {
  const db = getDb();
  await db.contasPagarReceber.delete(id);
}

export async function marcarContaPaga(
  id: string,
  pagoEm: string
): Promise<void> {
  const db = getDb();
  const conta = await db.contasPagarReceber.get(id);
  if (!conta) return;
  await db.contasPagarReceber.put({ ...conta, status: "pago", pagoEm });
}

export async function atualizarStatusVencidos(): Promise<void> {
  const db = getDb();
  const hoje = new Date().toISOString().slice(0, 10);
  const todas = await db.contasPagarReceber.toArray();
  const para = todas.filter(
    (c) => c.status === "pendente" && c.vencimento < hoje
  );
  if (para.length === 0) return;
  await db.contasPagarReceber.bulkPut(
    para.map((c) => ({ ...c, status: "atrasado" as const }))
  );
}
