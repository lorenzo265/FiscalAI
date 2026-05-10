import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  ContaBancaria,
  ContaPagarReceber,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import {
  gerarContasIniciais,
  gerarContasPagarReceberIniciais,
  gerarTransacoesIniciais,
} from "@/lib/mocks/controles";
import { BANCOS_OPENFINANCE } from "@/lib/mocks/seeds/bancos-openfinance";
import { pseudoUuid } from "@/lib/mocks/utils";

const SEED_KEY = "analista-fiscal:controles-seeded";

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

export async function listarContasBancarias(): Promise<ContaBancaria[]> {
  const db = getDb();
  const lista = await db.contasBancarias.toArray();
  return lista.sort((a, b) => a.conectadaEm.localeCompare(b.conectadaEm));
}

export async function obterContaBancaria(
  id: string
): Promise<ContaBancaria | undefined> {
  const db = getDb();
  return db.contasBancarias.get(id);
}

export async function sincronizarConta(id: string): Promise<ContaBancaria | undefined> {
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

export async function conectarNovaConta(
  empresa: Empresa,
  bancoId: string
): Promise<ContaBancaria> {
  const banco =
    BANCOS_OPENFINANCE.find((b) => b.id === bancoId) ??
    BANCOS_OPENFINANCE[0]!;
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

export async function listarTransacoes(
  contaId: string
): Promise<TransacaoBancaria[]> {
  const db = getDb();
  const lista = await db.transacoes.where("contaId").equals(contaId).toArray();
  return lista.sort((a, b) => b.data.localeCompare(a.data));
}

export async function listarTodasTransacoes(): Promise<TransacaoBancaria[]> {
  const db = getDb();
  const lista = await db.transacoes.toArray();
  return lista.sort((a, b) => b.data.localeCompare(a.data));
}

export async function conciliarTransacao(
  transacaoId: string,
  lancamentoId: string | null
): Promise<void> {
  const db = getDb();
  const tx = await db.transacoes.get(transacaoId);
  if (!tx) return;
  await db.transacoes.put({
    ...tx,
    conciliada: lancamentoId != null,
    lancamentoId: lancamentoId ?? undefined,
  });
}

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
