/**
 * Adapter de domínio: fiscal (Onda 1 / Fase C — integração com a API real).
 *
 * Fala com o backend FastAPI via `fetchJson` de `@/lib/http`, montando as rotas
 * com `getEmpresaIdAtiva()`. Endpoint real:
 *   - `POST /v1/empresas/{id}/apuracoes/das`  → calcula o DAS da competência.
 *   - `GET  /v1/empresas/{id}/apuracoes/{competencia}/das` → consulta calculado.
 *
 * Realidade do backend (descobertas por curl — ver handoff):
 *   - O `POST` calcula e **persiste** a apuração (`ApuracaoFiscal`). Repetir a
 *     mesma competência devolve 409 `ApuracaoJaExiste`; o `GET`-por-competência
 *     recupera a apuração calculada. Por isso `apuracaoAtual` tenta `GET` antes
 *     e só dispara `POST` quando ainda não há apuração da competência.
 *   - **Não existe** endpoint de "saúde fiscal" (health score) nem de série
 *     histórica/listagem de apurações. Esses dois mapeiam para estado vazio
 *     honesto (NÃO inventamos número). Ver `saude()` e `historico()` abaixo.
 *
 * Mapeamentos honestos:
 *   - `apuracaoAtual` → `POST .../apuracoes/das` da competência corrente.
 *   - `guias`         → deriva 1 guia da mesma apuração (sem endpoint de lista).
 *   - `saude`         → SEM endpoint → estado "sem dados" (score 0, sem alertas).
 *   - `historico`     → SEM endpoint/persistência → série vazia `[]`.
 *
 * Dono na integração: agente de domínio fiscal.
 */
import { z } from "zod";

import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import {
  apuracaoFiscalSchema,
  type ApuracaoFiscal,
  type FiscalHealth,
  type HistoricoMes,
} from "@/lib/schemas/fiscal";
import { type GuiaDAS } from "@/lib/schemas/guias";
import type { Empresa } from "@/lib/schemas/empresa";

// ── Shape REAL do backend (`ApuracaoDASOut`, já camelizado pelo fetchJson) ───
// Dinheiro chega como string decimal (NUMERIC). Mantemos string aqui; a
// conversão para `number` acontece só na fronteira do mapper, porque os schemas
// Zod das telas (e a aritmética delas) são `number` — espelha o que
// `mapearEmpresa` já faz com `faturamento_12m`.
const apuracaoDASOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  competencia: z.string(), // "YYYY-MM-DD" (primeiro dia do mês)
  tipo: z.string(),
  regime: z.string(),
  anexo: z.string(),
  anexoEfetivo: z.string(),
  faixa: z.number(),
  rbt12Usado: z.string(),
  aliquotaNominal: z.string(),
  aliquotaEfetiva: z.string(),
  receitaMes: z.string(),
  valorDas: z.string(),
  fatorR: z.string().nullable(),
  algoritmoVersao: z.string(),
  status: z.string(),
  uf: z.string().nullable().optional(),
  sublimiteAplicado: z.string().nullable().optional(),
  sublimiteExcedido: z.boolean().optional(),
});
type ApuracaoDASOut = z.infer<typeof apuracaoDASOutSchema>;

// Teto do Simples Nacional (LC 123 art. 3º, II). Não é alíquota tributável —
// é o limite-régua do regime, fixo em lei; usado só para a barra de progresso.
const TETO_SIMPLES = 4_800_000;
const SUBLIMITE_PADRAO = 3_600_000;

function dec(s: string | null | undefined): number {
  if (s == null) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function competenciaAtual(): string {
  const agora = new Date();
  const ano = agora.getFullYear();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  return `${ano}-${mes}`;
}

/** Vencimento do DAS: dia 20 do mês seguinte ao da competência (LC 123 art. 21). */
function vencimentoDAS(competenciaIso: string): string {
  const partes = competenciaIso.split("-");
  const ano = Number(partes[0] ?? 0);
  const mes = Number(partes[1] ?? 1);
  // mês é 1-based; Date usa 0-based → `mes` (sem -1) é o mês seguinte.
  const venc = new Date(ano, mes, 20);
  const y = venc.getFullYear();
  const m = String(venc.getMonth() + 1).padStart(2, "0");
  const d = String(venc.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function anoMesDaCompetencia(competencia: string): { ano: number; mes: number } {
  // backend devolve "YYYY-MM-DD"; aceita também "YYYY-MM".
  const partes = competencia.split("-");
  return { ano: Number(partes[0] ?? 0), mes: Number(partes[1] ?? 1) };
}

const ROTULO_MES = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

// ── Mapeamento ApuracaoDASOut → ApuracaoFiscal (schema das telas) ───────────
function mapearApuracao(
  out: ApuracaoDASOut,
  empresa: Empresa | null
): ApuracaoFiscal {
  const periodo = anoMesDaCompetencia(out.competencia);
  const valorDas = dec(out.valorDas);
  // faturamento 12m: rbt12 usado no cálculo (string decimal do backend).
  const fat12 = dec(out.rbt12Usado) || empresa?.faturamento12m || 0;
  const sublimite = dec(out.sublimiteAplicado) || SUBLIMITE_PADRAO;

  const fatorR =
    out.fatorR != null && (out.anexoEfetivo === "III" || out.anexoEfetivo === "V")
      ? {
          valor: dec(out.fatorR),
          anexoAtual: out.anexoEfetivo as "III" | "V",
          // Fator R < 28% empurra a atividade do Anexo III para o V (alíquota dobra).
          atencao: dec(out.fatorR) < 0.28,
        }
      : undefined;

  return apuracaoFiscalSchema.parse({
    periodo,
    faturamentoMes: dec(out.receitaMes),
    faturamento12m: fat12,
    sublimiteEstadual: sublimite,
    tetoSimples: TETO_SIMPLES,
    fatorR,
    aliquotaEfetiva: dec(out.aliquotaEfetiva),
    aliquotaNominal: dec(out.aliquotaNominal),
    faixa: out.faixa,
    valorDAS: valorDas,
    vencimento: vencimentoDAS(out.competencia),
    // `calculado` (backend) → `em_aberto` (vocabulário da tela: ainda não pago).
    status: out.status === "pago" ? "pago" : "em_aberto",
    // Backend não decompõe o DAS por tributo (IRPJ/CSLL/Cofins/…). Sem dado
    // honesto → composição vazia (a tela renderiza o donut vazio sem quebrar).
    composicao: [],
    alertas: [],
  });
}

// ── Mapeamento ApuracaoDASOut → GuiaDAS (deriva 1 guia da apuração) ─────────
function mapearGuia(out: ApuracaoDASOut): GuiaDAS {
  const periodo = anoMesDaCompetencia(out.competencia);
  const rotulo = `${ROTULO_MES[periodo.mes - 1] ?? "—"}/${periodo.ano}`;
  return {
    id: out.id,
    periodo,
    rotulo,
    // Número/código de barras/PIX só existem após emissão real da guia (não há
    // endpoint de emissão DAS aqui). Vazio = "guia ainda não emitida".
    numeroDocumento: "—",
    codigoBarras: "",
    faturamentoMes: dec(out.receitaMes),
    aliquotaEfetiva: dec(out.aliquotaEfetiva),
    valor: dec(out.valorDas),
    vencimento: vencimentoDAS(out.competencia),
    pagaEm: null,
    status: out.status === "pago" ? "pago" : "em_aberto",
    pixCopiaCola: "",
  };
}

// ── Chamada à API: obtém (ou calcula) o DAS da competência corrente ─────────
// GET-first → a apuração persiste no backend, então recuperamos a já calculada
// e só disparamos o POST quando ainda não existe (404). Isso torna a função
// idempotente: `apuracaoAtual` e `guias` chamam ambas no mesmo load da tela
// sem provocar 409 `ApuracaoJaExiste`. Se uma corrida criar a apuração entre o
// nosso GET e o POST, o 409 é recuperado com um GET final.
async function obterOuCalcularDAS(
  empresa: Empresa | null
): Promise<ApuracaoDASOut> {
  const empresaId = getEmpresaIdAtiva();
  if (!empresaId) {
    throw new ApiError(
      400,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada."
    );
  }

  const competencia = competenciaAtual(); // "YYYY-MM"
  const rotaGet = `/empresas/${empresaId}/apuracoes/${competencia}/das`;

  // 1. GET-first: a apuração da competência pode já ter sido calculada.
  try {
    return await fetchJson(rotaGet, apuracaoDASOutSchema);
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 404) throw err;
    // 404 → ainda não há apuração desta competência; segue para o cálculo.
  }

  // 2. POST: calcula e persiste. receita_mes é obrigatório e `gt=0` no backend.
  // Sem um faturamento mensal declarado, estimamos a média a partir do RBT12.
  const fat12 = empresa?.faturamento12m ?? 0;
  const receitaMes = fat12 > 0 ? fat12 / 12 : 0;
  if (receitaMes <= 0) {
    throw new ApiError(
      422,
      "FaturamentoIndisponivel",
      "Sem faturamento declarado para estimar a apuração do mês."
    );
  }

  const body: Record<string, string> = {
    competencia,
    // Dinheiro como string decimal — backend espera `Decimal`.
    receita_mes: receitaMes.toFixed(2),
  };
  // Anexo III/V exige folha_12m (Fator R). Sem esse dado no front, não enviamos
  // e o backend devolve `FatorRObrigatorio` — tratado em `mensagemAmigavel`.

  try {
    return await fetchJson(`/empresas/${empresaId}/apuracoes/das`, apuracaoDASOutSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    // Corrida: uma chamada concorrente (ex.: `guias` + `apuracaoAtual` no mesmo
    // load) já criou a apuração → 409. Recupera a apuração persistida via GET.
    if (err instanceof ApiError && err.status === 409) {
      return await fetchJson(rotaGet, apuracaoDASOutSchema);
    }
    throw err;
  }
}

/** Traduz `ApiError.codigo` em mensagem amigável (nunca vaza código cru). */
export function mensagemAmigavelFiscal(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível calcular sua apuração agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "ApuracaoJaExiste":
      return "A apuração deste mês já foi calculada.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa ativa.";
    case "RegimeIncompativel":
    case "EmpresaForaSimplesNacional":
      return "A apuração do DAS é exclusiva do Simples Nacional.";
    case "FatorRObrigatorio":
      return "Para o seu anexo, informe a folha de pagamento dos últimos 12 meses.";
    case "TabelaTributariaAusente":
      return "Tabela do Simples Nacional indisponível para esta competência.";
    case "FaturamentoIndisponivel":
      return "Sem faturamento declarado para estimar a apuração do mês.";
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para ver sua apuração.";
    default:
      return err.mensagem || "Não foi possível calcular sua apuração agora.";
  }
}

export const fiscal = {
  /**
   * GAP CONHECIDO: não há endpoint de "saúde fiscal" (Fiscal Health Score) no
   * backend. NÃO inventamos score. Retornamos um estado "sem dados" que as
   * telas (FiscalHealthScore, AlertasCard, ProximaObrigacaoCard) sabem
   * renderizar: score 0, tom warn, sem alertas, sem componentes.
   */
  saude: async (_empresa: Empresa | null): Promise<FiscalHealth> => {
    const vazio: FiscalHealth = {
      score: 0,
      tom: "warn",
      titulo: "Índice de saúde fiscal indisponível",
      descricao:
        "Ainda não há dados suficientes para calcular seu índice de saúde fiscal.",
      componentes: [],
      alertasPrioritarios: [],
      proximaObrigacao: {
        titulo: "Apuração do mês",
        descricao: "Confira sua apuração do DAS na aba Fiscal.",
        vencimento: vencimentoDAS(competenciaAtual()),
        acao: { label: "Ver apuração", rota: "/fiscal" },
      },
    };
    return Promise.resolve(vazio);
  },

  apuracaoAtual: async (empresa: Empresa | null): Promise<ApuracaoFiscal> => {
    const out = await obterOuCalcularDAS(empresa);
    return mapearApuracao(out, empresa);
  },

  /**
   * GAP CONHECIDO: não há endpoint de série histórica nem persistência de
   * apurações neste ambiente. NÃO fabricamos meses. Série vazia — a tela
   * renderiza o gráfico/lista vazios sem quebrar.
   */
  historico: async (
    _empresa: Empresa | null,
    _meses = 6
  ): Promise<HistoricoMes[]> => {
    return Promise.resolve([]);
  },

  /**
   * Sem endpoint de listagem/emissão de guias. Derivamos 1 guia da apuração da
   * competência corrente (o cálculo do DAS é a fonte). Número de documento /
   * código de barras / PIX ficam vazios (só existem após emissão real).
   */
  guias: async (empresa: Empresa | null): Promise<GuiaDAS[]> => {
    const out = await obterOuCalcularDAS(empresa);
    return [mapearGuia(out)];
  },
};
