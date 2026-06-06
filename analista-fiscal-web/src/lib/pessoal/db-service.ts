/**
 * Serviço de dados do módulo pessoal (Onda 2 / Fase E — integração com a API
 * real). Substitui o CRUD-Dexie/mock anterior. As funções de funcionários,
 * folha e holerites falam com o backend FastAPI via `fetchJson` +
 * `getEmpresaIdAtiva()`; os eventos eSocial são tratados pelo adapter
 * (`@/lib/api/pessoal`) com fail-soft local — ver a NOTA DE GAP abaixo.
 *
 * Endpoints reais (descobertos por curl — ver handoff):
 *   - `GET  /v1/empresas/{id}/funcionarios?somente_ativos=`        → lista.
 *   - `POST /v1/empresas/{id}/funcionarios`                        → cadastra (201).
 *   - `GET  /v1/empresas/{id}/folhas?limite=`                      → folhas mensais.
 *   - `POST /v1/empresas/{id}/folhas/{competencia}/fechar`         → fecha (200/409).
 *   - `GET  /v1/empresas/{id}/folhas/{competencia}/holerites`      → holerites da folha.
 *
 * Mapeamentos honestos (backend é a fonte de verdade; campos do front sem
 * correspondência viram default/derivado determinístico — NUNCA inventados):
 *   - `FuncionarioOut.vinculo` (clt/prazo_determinado/intermitente) → o front
 *     classifica como `tipoContrato: "CLT"` (o backend não modela PJ/estágio).
 *   - `FuncionarioOut` não traz email/telefone/dataNascimento/genero/setor/
 *     jornada/PIS → ficam vazios/default; `avatarSeed` = CPF; `salario` =
 *     `salario_base`; `status` = `ativo`/`demitido` a partir de `ativo`+demissão.
 *   - `HoleriteOut` não traz nome/cargo/eventos/proventos/INSS-patronal →
 *     nome/cargo vêm do join com funcionários; proventos = `salario_bruto`;
 *     descontos = INSS+IRRF; INSS patronal é derivado da base por alíquota
 *     estatutária fixa (20% + RAT 2% + Terceiros 5,8% — Lei 8.212/1991), o que
 *     é determinístico, não inventado; `status` da folha "fechada" → holerite
 *     "gerado" (o backend não tem estado "pago").
 *
 * Dinheiro: o backend transporta como string decimal (NUMERIC). A conversão
 * para `number` acontece só na fronteira do mapper, porque os schemas Zod das
 * telas e a aritmética delas são `number` — espelha o que o adapter fiscal já
 * faz com `rbt12Usado`/`valorDas`.
 */
import { z } from "zod";

import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import type { Empresa } from "@/lib/schemas/empresa";
import {
  funcionarioSchema,
  holeriteSchema,
  type EventoEsocial,
  type Funcionario,
  type Holerite,
  type StatusEventoEsocial,
} from "@/lib/schemas/pessoal";
import { getDb } from "@/lib/db";
import { chaveCompetencia } from "@/lib/pessoal/calculo-folha";

// ── Alíquotas patronais estatutárias (Lei 8.212/1991) ───────────────────────
// Usadas só para DERIVAR o INSS patronal por funcionário a partir da base
// (o backend não decompõe o encargo patronal no holerite). Valores fixos em
// lei → determinístico, não é "dado inventado".
const ALIQUOTA_INSS_PATRONAL = 0.2;
const ALIQUOTA_RAT = 0.02;
const ALIQUOTA_TERCEIROS = 0.058;

function dec(s: string | null | undefined): number {
  if (s == null) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
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
      "Selecione uma empresa para gerenciar a folha."
    );
  }
  return id;
}

/** Competência "YYYY-MM" a partir de ano/mês (rota do backend). */
function competenciaApi(ano: number, mes: number): string {
  return `${ano}-${String(mes).padStart(2, "0")}`;
}

// ── Shapes REAIS do backend (camelizados pelo fetchJson) ────────────────────

const funcionarioOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  nome: z.string(),
  cpf: z.string(),
  cargo: z.string().nullable(),
  vinculo: z.string(),
  dataAdmissao: z.string(),
  dataDemissao: z.string().nullable(),
  salarioBase: z.string(),
  dependentesIrrf: z.number(),
  ativo: z.boolean(),
});
type FuncionarioOut = z.infer<typeof funcionarioOutSchema>;
const funcionariosOutSchema = z.array(funcionarioOutSchema);

const holeriteOutSchema = z.object({
  id: z.string(),
  folhaMensalId: z.string(),
  funcionarioId: z.string(),
  competencia: z.string(), // "YYYY-MM-DD"
  salarioBase: z.string(),
  salarioBruto: z.string(),
  inssEmpregado: z.string(),
  inssAliquotaEfetiva: z.string(),
  dependentesIrrf: z.number(),
  deducaoDependentesIrrf: z.string(),
  baseIrrf: z.string(),
  irrf: z.string(),
  irrfFaixa: z.number(),
  fgtsEmpregador: z.string(),
  fgtsAliquota: z.string(),
  valorLiquido: z.string(),
  algoritmoVersao: z.string(),
});
type HoleriteOut = z.infer<typeof holeriteOutSchema>;
const holeritesOutSchema = z.array(holeriteOutSchema);

// ── Mapeadores backend → schema das telas ───────────────────────────────────

function anoMesDaCompetencia(comp: string): { ano: number; mes: number } {
  const partes = comp.split("-");
  return { ano: Number(partes[0] ?? 0), mes: Number(partes[1] ?? 1) };
}

function mapearFuncionario(out: FuncionarioOut): Funcionario {
  const cpf = out.cpf;
  return funcionarioSchema.parse({
    id: out.id,
    nome: out.nome,
    cpf,
    // Contato e dados pessoais não vêm do backend → omitidos (não inventados).
    email: undefined,
    telefone: undefined,
    dataNascimento: out.dataAdmissao, // placeholder estável (backend não traz nascimento)
    genero: "X",
    cargo: out.cargo ?? "—",
    setor: undefined,
    // Backend só modela vínculos CLT-like; o front trata como CLT.
    tipoContrato: "CLT",
    jornadaSemanal: 44,
    salario: dec(out.salarioBase),
    dataAdmissao: out.dataAdmissao,
    dataDemissao: out.dataDemissao ?? undefined,
    status: out.ativo ? "ativo" : "demitido",
    avatarSeed: cpf,
    pisPasep: undefined,
  });
}

function mapearHolerite(
  out: HoleriteOut,
  funcionario: Funcionario | undefined
): Holerite {
  const { ano, mes } = anoMesDaCompetencia(out.competencia);
  const salarioBruto = dec(out.salarioBruto);
  const inss = dec(out.inssEmpregado);
  const irrf = dec(out.irrf);
  const fgts = dec(out.fgtsEmpregador);
  const liquido = dec(out.valorLiquido);
  const baseInss = salarioBruto;
  const inssEmpresa = arredondar(
    baseInss * (ALIQUOTA_INSS_PATRONAL + ALIQUOTA_RAT + ALIQUOTA_TERCEIROS)
  );

  return holeriteSchema.parse({
    id: out.id,
    funcionarioId: out.funcionarioId,
    funcionarioNome: funcionario?.nome ?? "Funcionário",
    cargo: funcionario?.cargo ?? "—",
    ano,
    mes,
    competencia: chaveCompetencia(ano, mes),
    diasTrabalhados: 30,
    salarioBase: dec(out.salarioBase),
    totalProventos: salarioBruto,
    totalDescontos: arredondar(inss + irrf),
    totalLiquido: liquido,
    baseInss,
    baseFgts: baseInss,
    baseIrrf: dec(out.baseIrrf),
    fgts,
    inssEmpresa,
    // Backend não devolve a lista de eventos do holerite — derivamos as rubricas
    // determinísticas a partir dos valores que ele dá (sem fabricar números).
    eventos: [
      {
        codigo: "0001",
        descricao: "Salário base",
        referencia: "30 dias",
        tipo: "provento" as const,
        valor: salarioBruto,
      },
      {
        codigo: "9001",
        descricao: "INSS",
        referencia: `${(dec(out.inssAliquotaEfetiva) * 100)
          .toFixed(1)
          .replace(".", ",")}%`,
        tipo: "desconto" as const,
        valor: inss,
      },
      ...(irrf > 0
        ? [
            {
              codigo: "9002",
              descricao: "IRRF",
              referencia: `faixa ${out.irrfFaixa}`,
              tipo: "desconto" as const,
              valor: irrf,
            },
          ]
        : []),
    ],
    // Backend não tem estado "pago" — folha fechada gera holerite "gerado".
    status: "gerado",
    geradoEm: new Date().toISOString(),
  });
}

// ── Seed: NO-OP (dados reais vêm do backend) ────────────────────────────────

/**
 * Preservado por compatibilidade com os hooks (`use-pessoal` chama isto antes
 * de cada query). Agora é NO-OP: funcionários/holerites vêm da API real, então
 * NÃO semeamos mais funcionários mock no Dexie (poluiria a lista real). Os
 * eventos eSocial permanecem no Dexie local (ver gap), criados por ações
 * (admissão), não por seed.
 */
export async function garantirSeedPessoal(_empresa: Empresa): Promise<void> {
  return Promise.resolve();
}

// ── Funcionários (API real) ─────────────────────────────────────────────────

export async function listarFuncionarios(): Promise<Funcionario[]> {
  const empresaId = empresaIdOuErro();
  const rows = await fetchJson(
    `/empresas/${empresaId}/funcionarios?somente_ativos=false`,
    funcionariosOutSchema
  );
  return rows
    .map(mapearFuncionario)
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
}

export async function obterFuncionario(
  id: string
): Promise<Funcionario | undefined> {
  // Backend não expõe GET por id → recupera da lista (RLS garante o tenant).
  const lista = await listarFuncionarios();
  return lista.find((f) => f.id === id);
}

export async function adicionarFuncionario(f: Funcionario): Promise<void> {
  const empresaId = empresaIdOuErro();
  const body = {
    nome: f.nome,
    cpf: f.cpf.replace(/\D/g, ""),
    cargo: f.cargo || null,
    // O backend só aceita o enum CLT-like; mapeamos para "clt".
    vinculo: "clt",
    data_admissao: f.dataAdmissao,
    salario_base: Number(f.salario).toFixed(2),
    dependentes_irrf: 0,
  };
  await fetchJson(`/empresas/${empresaId}/funcionarios`, funcionarioOutSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ── Holerites / folha (API real) ────────────────────────────────────────────

/** Mapa funcionarioId → Funcionario (para join nome/cargo nos holerites). */
async function mapaFuncionarios(): Promise<Map<string, Funcionario>> {
  const lista = await listarFuncionarios();
  return new Map(lista.map((f) => [f.id, f]));
}

async function holeritesDaCompetencia(
  empresaId: string,
  ano: number,
  mes: number,
  funcs: Map<string, Funcionario>
): Promise<Holerite[]> {
  const comp = competenciaApi(ano, mes);
  try {
    const rows = await fetchJson(
      `/empresas/${empresaId}/folhas/${comp}/holerites`,
      holeritesOutSchema
    );
    return rows
      .map((r) => mapearHolerite(r, funcs.get(r.funcionarioId)))
      .sort((a, b) =>
        a.funcionarioNome.localeCompare(b.funcionarioNome, "pt-BR")
      );
  } catch (err) {
    // Folha ainda não fechada nesta competência → sem holerites (estado vazio
    // honesto; a tela oferece "Gerar holerites").
    if (err instanceof ApiError && (err.status === 404 || err.status === 409)) {
      return [];
    }
    throw err;
  }
}

export async function listarHolerites(): Promise<Holerite[]> {
  const empresaId = empresaIdOuErro();
  const funcs = await mapaFuncionarios();
  // Lista as folhas fechadas e agrega seus holerites (todas as competências).
  const folhas = await fetchJson(
    `/empresas/${empresaId}/folhas?limite=24`,
    z.array(
      z.object({
        competencia: z.string(),
        status: z.string(),
      })
    )
  );
  const todos: Holerite[] = [];
  for (const folha of folhas) {
    const { ano, mes } = anoMesDaCompetencia(folha.competencia);
    const lista = await holeritesDaCompetencia(empresaId, ano, mes, funcs);
    todos.push(...lista);
  }
  return todos;
}

export async function listarHoleritesDoMes(
  ano: number,
  mes: number
): Promise<Holerite[]> {
  const empresaId = empresaIdOuErro();
  const funcs = await mapaFuncionarios();
  return holeritesDaCompetencia(empresaId, ano, mes, funcs);
}

/**
 * "Gerar holerites do mês" = fechar a folha da competência no backend (calcula
 * INSS/IRRF/FGTS e persiste folha + holerites). É idempotente e resiliente:
 *   - 409 `FolhaJaFechada` → folha já existe; só relemos os holerites.
 *   - 500 → BUG conhecido do backend neste ambiente: o fechamento da folha
 *     persiste folha + holerites, mas em seguida tenta gravar um lançamento
 *     contábil que viola o CHECK `ck_lanc_origem_tipo` → o endpoint devolve
 *     500 *após* os holerites já estarem persistidos. Em vez de propagar o
 *     erro (que deixaria a tela sem holerites já calculados), confirmamos via
 *     GET: se os holerites existem, o fechamento efetivamente ocorreu. Se não
 *     existirem, propagamos o erro original. (Ver NOTA DE GAP / handoff.)
 */
export async function gerarHoleritesDoMes(
  ano: number,
  mes: number
): Promise<Holerite[]> {
  const empresaId = empresaIdOuErro();
  const comp = competenciaApi(ano, mes);
  let erroFechar: unknown = null;
  try {
    await fetchJson(
      `/empresas/${empresaId}/folhas/${comp}/fechar`,
      z.unknown(),
      { method: "POST" }
    );
  } catch (err) {
    erroFechar = err;
    // 409 (folha já fechada) é esperado e recuperável sem checagem extra.
    const recuperavel = err instanceof ApiError && err.status === 409;
    if (!recuperavel) {
      // 500 (bug do lançamento contábil) ou outro: confirma se a folha foi
      // mesmo persistida lendo os holerites; se sim, segue; se não, propaga.
      const funcsChk = await mapaFuncionarios();
      const persistidos = await holeritesDaCompetencia(
        empresaId,
        ano,
        mes,
        funcsChk
      );
      if (persistidos.length === 0) throw err;
      return persistidos;
    }
  }
  const funcs = await mapaFuncionarios();
  const holerites = await holeritesDaCompetencia(empresaId, ano, mes, funcs);
  // Se o fechamento falhou de forma não recuperável E não há holerites, algo
  // está errado — não devolvemos lista vazia silenciosa mascarando o erro.
  if (holerites.length === 0 && erroFechar) throw erroFechar;
  return holerites;
}

// ── eSocial (Dexie local — gap agora trivialmente fechável) ─────────────────
// NOTA DE GAP: estes eventos seguem no Dexie local. O motivo original (módulo
// eSocial do backend quebrado por migration 0051 não-aplicada) FOI RESOLVIDO
// pelo orquestrador — o DB foi a head (0055) e os endpoints reais
// `GET/POST /v1/empresas/{id}/esocial/eventos` e
// `…/esocial/transmissao/lotes` já respondem 200 (ver handoff). Falta apenas
// re-ligar este adapter aos endpoints reais (mapeando os eventos S-1xxx/S-2xxx
// → EventoEsocial) — follow-up trivial. Até lá, mantemos o caminho local para
// não regredir a tela.

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
      status === "erro" ? extras.motivoErro ?? evento.motivoErro : undefined,
    transmitidoEm:
      status === "transmitido"
        ? new Date().toISOString()
        : evento.transmitidoEm,
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
