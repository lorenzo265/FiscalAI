import { getDb } from "@/lib/db";
import type {
  Contraparte,
  NotaFiscal,
  ProdutoCatalogo,
  StatusManifesto,
} from "@/lib/schemas/nota";
import type { Empresa } from "@/lib/schemas/empresa";
import { gerarNotasIniciais } from "@/lib/mocks/notas";
import { CONTRAPARTES_MOCK } from "@/lib/mocks/seeds/contrapartes";
import { CATALOGO_PRODUTOS } from "@/lib/mocks/seeds/catalogo-produtos";

const SEED_KEY = "analista-fiscal:notas-seeded";

export async function garantirSeedNotas(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;
  const db = getDb();
  const total = await db.notas.count();
  if (total === 0) {
    const notas = gerarNotasIniciais(empresa);
    await db.notas.bulkPut(notas);
  }
  const totalContrapartes = await db.contrapartes.count();
  if (totalContrapartes === 0) {
    await db.contrapartes.bulkPut(CONTRAPARTES_MOCK);
  }
  const totalProdutos = await db.produtos.count();
  if (totalProdutos === 0) {
    await db.produtos.bulkPut(CATALOGO_PRODUTOS);
  }
  localStorage.setItem(flag, "1");
}

export async function listarNotas(): Promise<NotaFiscal[]> {
  const db = getDb();
  const lista = await db.notas.toArray();
  return lista.sort((a, b) => b.emitidaEm.localeCompare(a.emitidaEm));
}

export async function obterNota(chave: string): Promise<NotaFiscal | undefined> {
  const db = getDb();
  return db.notas.where("chave").equals(chave).first();
}

export async function salvarNota(nota: NotaFiscal): Promise<void> {
  const db = getDb();
  await db.notas.put(nota);
}

export async function cancelarNota(
  chave: string,
  motivo: string
): Promise<void> {
  const db = getDb();
  const nota = await obterNota(chave);
  if (!nota) return;
  await db.notas.put({
    ...nota,
    status: "cancelada",
    canceladaEm: new Date().toISOString(),
    motivoCancelamento: motivo,
  });
}

export async function adicionarCartaCorrecao(
  chave: string,
  texto: string
): Promise<void> {
  const db = getDb();
  const nota = await obterNota(chave);
  if (!nota) return;
  const cartas = nota.cartasCorrecao ?? [];
  await db.notas.put({
    ...nota,
    cartasCorrecao: [
      ...cartas,
      {
        sequencia: cartas.length + 1,
        texto,
        emitidaEm: new Date().toISOString(),
      },
    ],
  });
}

export async function manifestarNota(
  chave: string,
  manifesto: StatusManifesto
): Promise<void> {
  const db = getDb();
  const nota = await obterNota(chave);
  if (!nota) return;
  await db.notas.put({ ...nota, manifesto });
}

export async function listarContrapartes(): Promise<Contraparte[]> {
  const db = getDb();
  return db.contrapartes.toArray();
}

export async function salvarContraparte(c: Contraparte): Promise<void> {
  const db = getDb();
  await db.contrapartes.put(c);
}

export async function listarProdutos(): Promise<ProdutoCatalogo[]> {
  const db = getDb();
  return db.produtos.toArray();
}
