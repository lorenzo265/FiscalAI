import { getDb } from "@/lib/db";
import type { LancamentoContabil } from "@/lib/schemas/contabil";
import type { Empresa } from "@/lib/schemas/empresa";
import {
  gerarLancamentosBancariosMock,
  gerarLancamentosDeNotas,
} from "@/lib/contabil/geracao";
import { listarNotas, garantirSeedNotas } from "@/lib/notas/db-service";

const SEED_KEY = "analista-fiscal:contabil-seeded";

export async function garantirSeedContabil(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;

  await garantirSeedNotas(empresa);
  const db = getDb();
  const total = await db.lancamentos.count();
  if (total === 0) {
    const notas = await listarNotas();
    const lancamentos = [
      ...gerarLancamentosBancariosMock(empresa),
      ...gerarLancamentosDeNotas(notas),
    ];
    await db.lancamentos.bulkPut(lancamentos);
  }
  localStorage.setItem(flag, "1");
}

export async function listarLancamentos(): Promise<LancamentoContabil[]> {
  const db = getDb();
  const lista = await db.lancamentos.toArray();
  return lista.sort((a, b) => a.data.localeCompare(b.data));
}

export async function adicionarLancamento(
  lancamento: LancamentoContabil
): Promise<void> {
  const db = getDb();
  await db.lancamentos.put(lancamento);
}

export async function removerLancamento(id: string): Promise<void> {
  const db = getDb();
  await db.lancamentos.delete(id);
}
