import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type { MensagemAssistente } from "@/lib/schemas/assistente";
import { gerarResposta, mensagemSaudacao } from "@/lib/mocks/assistente";
import { pseudoUuid } from "@/lib/mocks/utils";

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

export async function enviarPergunta(
  empresa: Empresa,
  pergunta: string
): Promise<{ pergunta: MensagemAssistente; resposta: MensagemAssistente }> {
  const usuario: MensagemAssistente = {
    id: `msg-${pseudoUuid().slice(0, 10)}`,
    role: "user",
    texto: pergunta.trim(),
    blocos: [],
    citacoes: [],
    sugestoes: [],
    criadoEm: new Date().toISOString(),
  };
  await adicionarMensagem(usuario);

  const resposta = await gerarResposta(pergunta, empresa);
  await adicionarMensagem(resposta);

  return { pergunta: usuario, resposta };
}
