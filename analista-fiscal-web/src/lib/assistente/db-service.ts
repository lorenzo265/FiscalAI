/**
 * db-service do assistente — agora SÓ histórico LOCAL (Dexie).
 *
 * A geração de resposta migrou para o backend real (ver `src/lib/api/assistente.ts`,
 * que persiste pergunta+resposta via `adicionarMensagem`). O backend não expõe
 * endpoint de histórico de chat (o módulo `memoria` é grafo de fatos, não
 * transcrição) → a transcrição vive aqui. O seed (`mensagemSaudacao`) é uma
 * saudação local, não um fato fiscal fabricado.
 */
import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type { MensagemAssistente } from "@/lib/schemas/assistente";
import { mensagemSaudacao } from "@/lib/mocks/assistente";

const SEED_KEY = "analista-fiscal:assistente-seeded";

export async function garantirSeedAssistente(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;
  const db = getDb();
  if ((await db.mensagensAssistente.count()) === 0) {
    await db.mensagensAssistente.put(mensagemSaudacao(empresa));
  }
  localStorage.setItem(flag, "1");
}

export async function listarMensagens(): Promise<MensagemAssistente[]> {
  const db = getDb();
  const lista = await db.mensagensAssistente.toArray();
  return lista.sort((a, b) => a.criadoEm.localeCompare(b.criadoEm));
}

export async function adicionarMensagem(
  msg: MensagemAssistente
): Promise<void> {
  const db = getDb();
  await db.mensagensAssistente.put(msg);
}

export async function limparMensagens(): Promise<void> {
  const db = getDb();
  await db.mensagensAssistente.clear();
}
