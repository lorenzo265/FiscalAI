/**
 * Adapter de domínio: agenda — calendário fiscal (Onda 1 / Fase C).
 *
 * Fala com o backend FastAPI real via `fetchJson`, montando rotas
 * `/v1/empresas/{empresa_id}/agenda` a partir de `getEmpresaIdAtiva()`.
 *
 * Contrato real (descoberto via OpenAPI + curl contra :8000):
 *  - `GET  /v1/empresas/{id}/agenda?ano=YYYY` → `AgendaListaOut`
 *      `{ empresa_id, ano, total, itens: AgendaItemOut[] }`.
 *  - `POST /v1/empresas/{id}/agenda/gerar` body `{ ano, tem_funcionarios?, parcelar_irpj? }`
 *      → mesmo `AgendaListaOut` (201). Idempotente: regera o ano.
 *  - `AgendaItemOut` (snake → camel após `toCamel`):
 *      `id`, `titulo`, `descricao|null`, `data_vencimento` (date `YYYY-MM-DD`),
 *      `regime`, `tipo_obrigacao`, `status` (`pendente|concluido|vencido`).
 *
 * GERAÇÃO SOB DEMANDA: a agenda NÃO é populada automaticamente. O `GET`
 * devolve `total: 0` até alguém chamar `/gerar`. Para que a tela "apareça",
 * `listar`/`listarAno` fazem **fallback**: se o ano vier vazio, dispara o
 * `POST …/gerar` (com `tem_funcionarios` derivado do perfil da empresa) e
 * retorna o resultado. Idempotente — chamar de novo só regenera o mesmo ano.
 *
 * MAPEAMENTO para o `EventoAgenda` do front (preserva o que as telas usam:
 * `status`, `data`, `titulo`, `descricao`, `id`, `tipo`):
 *  - `data_vencimento` → `data` (ISO `YYYY-MM-DD`, igual ao mock).
 *  - `status` backend → front: `concluido→pago`, `vencido→atrasado`,
 *    `pendente→pendente`. (`informativo` do front fica sem origem no backend.)
 *  - `tipo_obrigacao` → `tipo` (enum do front): impostos/DARFs → `imposto`;
 *    DEFIS/DASN/DCTFWeb/DIRF → `obrigacao_acessoria`; FGTS → `folha`;
 *    eSocial → `esocial`; desconhecido → `informativo`.
 *  - `valor`/`rota` não existem no backend → ficam `undefined` (NÃO inventados).
 *
 * Filtro de mês (`listarMes`): o backend só filtra por **ano**. Filtramos o
 * mês client-side a partir da lista anual (documentado abaixo).
 */
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import { ApiError, fetchJson, toSnake } from "@/lib/http";
import {
  agendaListaOutSchema,
  eventosAgendaSchema,
  type AgendaItemOut,
  type EventoAgenda,
} from "@/lib/schemas/agenda";
import type { Empresa } from "@/lib/schemas/empresa";

// ── mapeamento status backend → front ────────────────────────────────────────

const STATUS_BACKEND_PARA_FRONT: Record<
  string,
  EventoAgenda["status"]
> = {
  pendente: "pendente",
  concluido: "pago",
  vencido: "atrasado",
};

// ── mapeamento tipo_obrigacao → tipo (enum do front) ─────────────────────────

const TIPO_OBRIGACAO_PARA_TIPO: Record<string, EventoAgenda["tipo"]> = {
  // impostos / DARFs / guias com pagamento
  pgdas_d: "imposto",
  das_mei: "imposto",
  pis_cofins: "imposto",
  irpj_csll_trimestral: "imposto",
  gps_inss: "imposto",
  // declarações / obrigações acessórias
  defis: "obrigacao_acessoria",
  dasn_simei: "obrigacao_acessoria",
  dctf_web: "obrigacao_acessoria",
  dirf: "obrigacao_acessoria",
  // folha / trabalhista
  fgts: "folha",
  // eSocial
  esocial_s1200: "esocial",
};

function mapearTipo(tipoObrigacao: string): EventoAgenda["tipo"] {
  return TIPO_OBRIGACAO_PARA_TIPO[tipoObrigacao] ?? "informativo";
}

function mapearStatus(status: string): EventoAgenda["status"] {
  return STATUS_BACKEND_PARA_FRONT[status] ?? "pendente";
}

/** `AgendaItemOut` (backend, camelizado) → `EventoAgenda` (contrato do front). */
function mapearItem(item: AgendaItemOut): EventoAgenda {
  return {
    id: item.id,
    data: item.dataVencimento,
    titulo: item.titulo,
    descricao: item.descricao ?? "",
    tipo: mapearTipo(item.tipoObrigacao),
    status: mapearStatus(item.status),
    // valor/rota não existem no backend — deixados undefined (não inventados).
  };
}

// ── tradução de erro de domínio ──────────────────────────────────────────────

function mensagemAmigavelAgenda(err: ApiError): string {
  switch (err.codigo) {
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa válida.";
    case "REGIME_NAO_SUPORTADO_AGENDA":
      return "O calendário fiscal automático ainda não cobre o regime desta empresa.";
    default:
      return err.mensagem || "Não foi possível carregar a agenda fiscal.";
  }
}

// ── helpers de rota ──────────────────────────────────────────────────────────

function exigirEmpresaId(): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      0,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada."
    );
  }
  return id;
}

/** Deriva `tem_funcionarios` do perfil da empresa para a geração sob demanda. */
function temFuncionarios(empresa: Empresa | null): boolean {
  const perfil = empresa?.perfilUi ?? "";
  // perfis "…_com_funcionarios"; default conservador = false (SN sem folha).
  return perfil.includes("com_funcionarios") || perfil.includes("funcionarios");
}

async function buscarAno(empresaId: string, ano: number): Promise<EventoAgenda[]> {
  const resposta = await fetchJson(
    `/empresas/${empresaId}/agenda?ano=${ano}`,
    agendaListaOutSchema
  );
  return resposta.itens.map(mapearItem);
}

async function gerarAno(
  empresaId: string,
  ano: number,
  empresa: Empresa | null
): Promise<EventoAgenda[]> {
  const body = toSnake({ ano, temFuncionarios: temFuncionarios(empresa) });
  const resposta = await fetchJson(
    `/empresas/${empresaId}/agenda/gerar`,
    agendaListaOutSchema,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  return resposta.itens.map(mapearItem);
}

/**
 * Carrega o ano; se vier vazio, gera sob demanda e devolve o resultado.
 * Centraliza o fallback de geração para `listar`/`listarMes`/`listarAno`.
 */
async function carregarAnoComGeracao(
  ano: number,
  empresa: Empresa | null
): Promise<EventoAgenda[]> {
  try {
    const empresaId = exigirEmpresaId();
    const eventos = await buscarAno(empresaId, ano);
    if (eventos.length > 0) return eventos;
    // Agenda gerada sob demanda — popula na primeira visita.
    return await gerarAno(empresaId, ano, empresa);
  } catch (err) {
    if (err instanceof ApiError) {
      throw new ApiError(err.status, err.codigo, mensagemAmigavelAgenda(err));
    }
    throw err;
  }
}

export const agenda = {
  /**
   * Lista a agenda (mês corrente usa a lista anual; a tela home agrupa por dia).
   * Mantém a assinatura `(empresa)` — usa o ano corrente.
   */
  listar: (empresa: Empresa | null): Promise<EventoAgenda[]> => {
    const ano = new Date().getFullYear();
    return carregarAnoComGeracao(ano, empresa);
  },

  /**
   * Lista os eventos de um mês. O backend só filtra por ano → filtramos o mês
   * client-side a partir da lista anual.
   */
  listarMes: async (
    empresa: Empresa | null,
    ano: number,
    mes: number
  ): Promise<EventoAgenda[]> => {
    const eventos = await carregarAnoComGeracao(ano, empresa);
    const prefixo = `${ano}-${String(mes).padStart(2, "0")}`;
    return eventos.filter((e) => e.data.startsWith(prefixo));
  },

  /** Lista todos os eventos do ano. */
  listarAno: (empresa: Empresa | null, ano: number): Promise<EventoAgenda[]> =>
    carregarAnoComGeracao(ano, empresa),
};

// Re-export para consumidores que ainda usem o schema de array (compat).
export { eventosAgendaSchema };
