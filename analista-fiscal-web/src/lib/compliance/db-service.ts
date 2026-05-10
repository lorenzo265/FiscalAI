import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Certidao,
  CompliancePainel,
  Intimacao,
  Parcelamento,
  StatusIntimacao,
} from "@/lib/schemas/compliance";
import {
  calcularStatusCertidao,
  gerarCertidaoRenovada,
  gerarCertidoesIniciais,
  gerarIntimacoesIniciais,
  gerarParcelamentosIniciais,
} from "@/lib/mocks/compliance";

const SEED_KEY = "analista-fiscal:compliance-seeded";

export async function garantirSeedCompliance(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;

  const db = getDb();
  if ((await db.certidoes.count()) === 0) {
    await db.certidoes.bulkPut(gerarCertidoesIniciais(empresa));
  }
  if ((await db.intimacoes.count()) === 0) {
    await db.intimacoes.bulkPut(gerarIntimacoesIniciais(empresa));
  }
  if ((await db.parcelamentos.count()) === 0) {
    await db.parcelamentos.bulkPut(gerarParcelamentosIniciais(empresa));
  }
  localStorage.setItem(flag, "1");
}

export async function listarCertidoes(): Promise<Certidao[]> {
  const db = getDb();
  const lista = await db.certidoes.toArray();
  // Recalcula status baseado em data de hoje
  const hoje = new Date();
  return lista
    .map((c) => ({ ...c, status: calcularStatusCertidao(c.vencimento, hoje) }))
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));
}

export async function renovarCertidao(id: string): Promise<Certidao | undefined> {
  const db = getDb();
  const antiga = await db.certidoes.get(id);
  if (!antiga) return undefined;
  // Substitui a antiga pela renovada (mantém o id externo do tipo p/ navegação intuitiva)
  const renovada = gerarCertidaoRenovada(antiga);
  await db.certidoes.delete(id);
  await db.certidoes.put(renovada);
  return renovada;
}

export async function listarIntimacoes(): Promise<Intimacao[]> {
  const db = getDb();
  const lista = await db.intimacoes.toArray();
  return lista.sort((a, b) => b.recebidoEm.localeCompare(a.recebidoEm));
}

export async function obterIntimacao(id: string): Promise<Intimacao | undefined> {
  const db = getDb();
  return db.intimacoes.get(id);
}

export async function atualizarStatusIntimacao(
  id: string,
  status: StatusIntimacao
): Promise<void> {
  const db = getDb();
  const intim = await db.intimacoes.get(id);
  if (!intim) return;
  await db.intimacoes.put({ ...intim, status });
}

export async function enviarIntimacaoAoContador(id: string): Promise<void> {
  const db = getDb();
  const intim = await db.intimacoes.get(id);
  if (!intim) return;
  await db.intimacoes.put({ ...intim, enviadoContador: true });
}

export async function listarParcelamentos(): Promise<Parcelamento[]> {
  const db = getDb();
  return db.parcelamentos.toArray();
}

export async function compliancePainel(): Promise<CompliancePainel> {
  const [certidoes, intimacoes, parcelamentos] = await Promise.all([
    listarCertidoes(),
    listarIntimacoes(),
    listarParcelamentos(),
  ]);
  const vigentes = certidoes.filter((c) => c.status === "vigente");
  const intimacoesAbertas = intimacoes.filter(
    (i) => i.status !== "respondida" && i.status !== "encerrada"
  );
  const proximas = certidoes
    .filter((c) => c.status !== "vencida")
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));
  return {
    certidoesVigentes: vigentes.length,
    certidoesTotal: certidoes.length,
    intimacoesAbertas: intimacoesAbertas.length,
    intimacoesTotal: intimacoes.length,
    parcelamentosAtivos: parcelamentos.filter((p) => p.status === "ativo")
      .length,
    cnpjAtivo: true,
    proximaCertidaoVencimento: proximas[0]?.vencimento ?? null,
  };
}
