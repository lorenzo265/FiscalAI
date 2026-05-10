import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  EventoEsocial,
  Funcionario,
  Holerite,
  StatusEventoEsocial,
} from "@/lib/schemas/pessoal";
import {
  gerarEventosEsocialIniciais,
  gerarFuncionariosIniciais,
  gerarHoleritesIniciais,
} from "@/lib/mocks/pessoal";
import { calcularHolerite, chaveCompetencia } from "@/lib/pessoal/calculo-folha";

const SEED_KEY = "analista-fiscal:pessoal-seeded";

export async function garantirSeedPessoal(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;

  const db = getDb();
  if ((await db.funcionarios.count()) === 0) {
    const funcionarios = gerarFuncionariosIniciais(empresa);
    await db.funcionarios.bulkPut(funcionarios);
    const holerites = gerarHoleritesIniciais(funcionarios, 6);
    await db.holerites.bulkPut(holerites);
    const eventos = gerarEventosEsocialIniciais(funcionarios, holerites);
    await db.eventosEsocial.bulkPut(eventos);
  }

  localStorage.setItem(flag, "1");
}

export async function listarFuncionarios(): Promise<Funcionario[]> {
  const db = getDb();
  const lista = await db.funcionarios.toArray();
  return lista.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
}

export async function obterFuncionario(
  id: string
): Promise<Funcionario | undefined> {
  const db = getDb();
  return db.funcionarios.get(id);
}

export async function adicionarFuncionario(f: Funcionario): Promise<void> {
  const db = getDb();
  await db.funcionarios.put(f);
}

export async function listarHolerites(): Promise<Holerite[]> {
  const db = getDb();
  return db.holerites.toArray();
}

export async function listarHoleritesDoMes(
  ano: number,
  mes: number
): Promise<Holerite[]> {
  const db = getDb();
  const competencia = chaveCompetencia(ano, mes);
  const lista = await db.holerites
    .where("competencia")
    .equals(competencia)
    .toArray();
  return lista.sort((a, b) =>
    a.funcionarioNome.localeCompare(b.funcionarioNome, "pt-BR")
  );
}

export async function gerarHoleritesDoMes(
  ano: number,
  mes: number
): Promise<Holerite[]> {
  const db = getDb();
  const funcionarios = await db.funcionarios.toArray();
  const ativos = funcionarios.filter((f) => f.status !== "demitido");
  const novos = ativos.map((f) =>
    calcularHolerite({
      funcionario: f,
      ano,
      mes,
      diasTrabalhados: f.status === "afastado" ? 18 : 30,
    })
  );
  await db.holerites.bulkPut(novos);
  return novos;
}

export async function listarEventosEsocial(): Promise<EventoEsocial[]> {
  const db = getDb();
  const lista = await db.eventosEsocial.toArray();
  return lista.sort((a, b) => b.criadoEm.localeCompare(a.criadoEm));
}

export async function adicionarEventoEsocial(
  evento: EventoEsocial
): Promise<void> {
  const db = getDb();
  await db.eventosEsocial.put(evento);
}

export async function atualizarStatusEvento(
  id: string,
  status: StatusEventoEsocial,
  extras: { recibo?: string; motivoErro?: string } = {}
): Promise<void> {
  const db = getDb();
  const evento = await db.eventosEsocial.get(id);
  if (!evento) return;
  await db.eventosEsocial.put({
    ...evento,
    status,
    recibo: extras.recibo ?? evento.recibo,
    motivoErro:
      status === "erro"
        ? extras.motivoErro ?? evento.motivoErro
        : undefined,
    transmitidoEm:
      status === "transmitido" ? new Date().toISOString() : evento.transmitidoEm,
  });
}

export async function transmitirEventosDoMes(
  ano: number,
  mes: number
): Promise<{ transmitidos: number }> {
  const db = getDb();
  const competencia = chaveCompetencia(ano, mes);
  const eventos = await db.eventosEsocial
    .where("competencia")
    .equals(competencia)
    .toArray();
  const pendentes = eventos.filter(
    (e) => e.status === "pendente" || e.status === "rascunho"
  );
  if (pendentes.length === 0) return { transmitidos: 0 };
  await db.eventosEsocial.bulkPut(
    pendentes.map((e) => ({
      ...e,
      status: "transmitido" as const,
      recibo: `R-${cryptoLikeId()}`,
      transmitidoEm: new Date().toISOString(),
    }))
  );
  return { transmitidos: pendentes.length };
}

function cryptoLikeId(): string {
  return Math.random().toString(36).slice(2, 10).toUpperCase();
}
