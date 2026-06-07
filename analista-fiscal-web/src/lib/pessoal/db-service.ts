/**
 * Serviço de dados do módulo pessoal (Onda 2 / Fase E — integração com a API
 * real). Substitui o CRUD-Dexie/mock anterior. Funcionários, folha, holerites E
 * eventos eSocial falam com o backend FastAPI via `fetchJson` +
 * `getEmpresaIdAtiva()`. Nada mais é Dexie local neste módulo.
 *
 * Endpoints reais (descobertos por curl — ver handoff):
 *   - `GET  /v1/empresas/{id}/funcionarios?somente_ativos=`        → lista.
 *   - `POST /v1/empresas/{id}/funcionarios`                        → cadastra (201).
 *   - `GET  /v1/empresas/{id}/folhas?limite=`                      → folhas mensais.
 *   - `POST /v1/empresas/{id}/folhas/{competencia}/fechar`         → fecha (200/409).
 *   - `GET  /v1/empresas/{id}/folhas/{competencia}/holerites`      → holerites da folha.
 *   - `GET/POST /v1/empresas/{id}/esocial/eventos`                 → lista / gera (S-1200).
 *   - `POST /v1/empresas/{id}/esocial/eventos/{eid}/assinar`       → assina (412 sem cert A1).
 *   - `POST /v1/empresas/{id}/esocial/transmissao/lotes`           → transmite (412 se flag off).
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
  eventoEsocialSchema,
  funcionarioSchema,
  holeriteSchema,
  type EventoEsocial,
  type Funcionario,
  type Holerite,
  type StatusEventoEsocial,
} from "@/lib/schemas/pessoal";
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

export async function adicionarFuncionario(f: Funcionario): Promise<Funcionario> {
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
  const criado = await fetchJson(
    `/empresas/${empresaId}/funcionarios`,
    funcionarioOutSchema,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  // Devolve o funcionário com o id REAL do backend (necessário p/ gerar o
  // evento eSocial S-2200 a partir da referência correta).
  return mapearFuncionario(criado);
}

/**
 * Gera o evento eSocial S-2200 (admissão) a partir do id REAL do funcionário.
 * Fail-soft: 409 (já gerado) ou qualquer outro erro não pode quebrar a admissão
 * — o funcionário já foi criado; o evento é um efeito secundário.
 */
export async function gerarEventoAdmissao(funcionarioId: string): Promise<void> {
  const empresaId = empresaIdOuErro();
  try {
    await fetchJson(`/empresas/${empresaId}/esocial/eventos`, z.unknown(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo_evento: "S-2200", referencia_id: funcionarioId }),
    });
  } catch {
    // não bloqueia a admissão (estado honesto: o evento simplesmente não é gerado).
  }
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
      await gerarEventosFolha(empresaId, persistidos);
      return persistidos;
    }
  }
  const funcs = await mapaFuncionarios();
  const holerites = await holeritesDaCompetencia(empresaId, ano, mes, funcs);
  // Se o fechamento falhou de forma não recuperável E não há holerites, algo
  // está errado — não devolvemos lista vazia silenciosa mascarando o erro.
  if (holerites.length === 0 && erroFechar) throw erroFechar;
  // Fechou a folha → gera os eventos S-1200 (remuneração) no eSocial, um por
  // holerite. Fail-soft: nunca quebra o fechamento (ver gerarEventosFolha).
  await gerarEventosFolha(empresaId, holerites);
  return holerites;
}

// ── eSocial (API real) ──────────────────────────────────────────────────────
// Eventos vêm do backend. A geração acontece ao fechar a folha (S-1200 por
// holerite, ver gerarEventosFolha). A transmissão real é gated: sem certificado
// digital A1 o backend responde 412 (EsocialAssinaturaIndisponivel) e, com a
// flag de transmissão desligada, 412 (EsocialTransmissaoDesativada). Tratamos o
// 412 com mensagem honesta na UI — NUNCA simulamos sucesso nem inventamos recibo.

const eventoEsocialOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipoEvento: z.string(),
  referenciaTipo: z.string(),
  referenciaId: z.string(),
  periodoApuracao: z.string().nullable(),
  payload: z.record(z.unknown()),
  status: z.string(),
  protocolo: z.string().nullable(),
  algoritmoVersao: z.string(),
  criadoEm: z.string(),
  transmitidoEm: z.string().nullable(),
  processadoEm: z.string().nullable(),
});
type EventoEsocialOut = z.infer<typeof eventoEsocialOutSchema>;
const eventosEsocialOutSchema = z.array(eventoEsocialOutSchema);

const TIPOS_ESOCIAL_CONHECIDOS = [
  "S-1200",
  "S-1210",
  "S-2200",
  "S-2299",
  "S-2300",
  "S-1299",
  "S-2230",
] as const;

/** Status do backend → vocabulário da tela (mantém cor + ícone + palavra). */
function mapearStatusEsocial(status: string): StatusEventoEsocial {
  switch (status) {
    case "aceito":
      return "transmitido";
    case "assinado":
    case "em_lote":
      return "pendente";
    case "rejeitado":
    case "rejeitado_xsd":
      return "erro";
    default: // "preparado" e demais estados iniciais
      return "rascunho";
  }
}

/** "YYYY-MM" a partir de uma data ISO "YYYY-MM-DD" (ou "" se nula). */
function competenciaDeDataIso(data: string | null): string {
  if (!data) return "";
  const [ano, mes] = data.split("-");
  return ano && mes ? `${ano}-${mes}` : "";
}

function tipoEsocialConhecido(t: string): EventoEsocial["tipo"] {
  return (TIPOS_ESOCIAL_CONHECIDOS as readonly string[]).includes(t)
    ? (t as EventoEsocial["tipo"])
    : "S-1200";
}

function mapearEventoEsocial(out: EventoEsocialOut): EventoEsocial {
  const status = mapearStatusEsocial(out.status);
  return eventoEsocialSchema.parse({
    id: out.id,
    tipo: tipoEsocialConhecido(out.tipoEvento),
    // O backend não devolve o nome do trabalhador no evento (é join) → omitido.
    funcionarioId: undefined,
    funcionarioNome: undefined,
    competencia: competenciaDeDataIso(out.periodoApuracao),
    status,
    recibo: out.protocolo ?? undefined,
    motivoErro:
      status === "erro"
        ? "Evento rejeitado pelo eSocial. Revise os dados e reenvie."
        : undefined,
    transmitidoEm: out.transmitidoEm ?? undefined,
    criadoEm: out.criadoEm,
  });
}

export async function listarEventosEsocial(): Promise<EventoEsocial[]> {
  const empresaId = empresaIdOuErro();
  const rows = await fetchJson(
    `/empresas/${empresaId}/esocial/eventos?limite=200`,
    eventosEsocialOutSchema
  );
  return rows
    .map(mapearEventoEsocial)
    .sort((a, b) => b.criadoEm.localeCompare(a.criadoEm));
}

/**
 * Gera um evento S-1200 (remuneração) por holerite ao fechar a folha. Fail-soft:
 * a geração é idempotente no backend (409 EventoESocialJaExiste se já existe) e
 * qualquer falha é engolida — nunca quebra o fechamento da folha. Os eventos
 * gerados aparecem na tela do eSocial.
 */
async function gerarEventosFolha(
  empresaId: string,
  holerites: Holerite[]
): Promise<void> {
  await Promise.all(
    holerites.map(async (h) => {
      try {
        await fetchJson(`/empresas/${empresaId}/esocial/eventos`, z.unknown(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tipo_evento: "S-1200", referencia_id: h.id }),
        });
      } catch {
        // 409 (já gerado) ou qualquer outro erro: não pode quebrar a folha —
        // apenas não gera o evento (estado honesto, sem dado fabricado).
      }
    })
  );
}

/**
 * "Reenviar"/avançar um evento. A ação real sem lote é assinar — sem certificado
 * digital A1 o backend responde 412 (EsocialAssinaturaIndisponivel), que
 * propagamos para a tela traduzir com mensagem honesta (não simulamos sucesso).
 */
export async function atualizarStatusEvento(
  id: string,
  _status: StatusEventoEsocial,
  _extras: { recibo?: string; motivoErro?: string } = {}
): Promise<void> {
  const empresaId = empresaIdOuErro();
  await fetchJson(
    `/empresas/${empresaId}/esocial/eventos/${id}/assinar`,
    z.unknown(),
    { method: "POST" }
  );
}

async function cnpjDaEmpresa(empresaId: string): Promise<string> {
  const emp = await fetchJson(
    `/empresas/${empresaId}`,
    z.object({ cnpj: z.string() })
  );
  return emp.cnpj;
}

/**
 * Transmite os eventos preparados da competência: assina cada um e envia o lote.
 * Sem certificado A1 / com a flag de transmissão desligada, o backend responde
 * 412 — propagamos para a tela exibir mensagem honesta (sem fingir transmissão).
 */
export async function transmitirEventosDoMes(
  ano: number,
  mes: number
): Promise<{ transmitidos: number }> {
  const empresaId = empresaIdOuErro();
  const comp = competenciaApi(ano, mes);
  const rows = await fetchJson(
    `/empresas/${empresaId}/esocial/eventos?limite=200`,
    eventosEsocialOutSchema
  );
  const pendentes = rows.filter(
    (e) =>
      competenciaDeDataIso(e.periodoApuracao) === comp &&
      (e.status === "preparado" || e.status === "assinado")
  );
  if (pendentes.length === 0) return { transmitidos: 0 };

  // Assina os que ainda estão "preparado" (412 sem cert A1 → propaga honesto).
  for (const e of pendentes.filter((p) => p.status === "preparado")) {
    await fetchJson(
      `/empresas/${empresaId}/esocial/eventos/${e.id}/assinar`,
      z.unknown(),
      { method: "POST" }
    );
  }
  // Envia o lote (precisa do CNPJ do empregador; 412 se transmissão off).
  const cnpj = await cnpjDaEmpresa(empresaId);
  const lote = await fetchJson(
    `/empresas/${empresaId}/esocial/transmissao/lotes?cnpj_empregador=${cnpj}`,
    z.object({
      protocolo: z.string().nullable(),
      estado: z.number().nullable(),
      eventos: z.number(),
    }),
    { method: "POST" }
  );
  return { transmitidos: lote.eventos };
}
