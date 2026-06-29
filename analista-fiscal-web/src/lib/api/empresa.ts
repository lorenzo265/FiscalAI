/**
 * Adapter de domínio: empresa (Fase B — Auth & Empresa). HTTP real.
 *
 * Endpoints (ver `hadoff-front-back.md` › Apêndice):
 *   - `GET  /v1/empresas`               → lista (RLS via JWT)
 *   - `GET  /v1/empresas/{id}`          → uma empresa
 *   - `POST /v1/empresas`               → cria (EmpresaIn)
 *   - `POST /v1/empresas/onboarding`    → lookup CNPJ (BrasilAPI) + auto-cria
 *
 * Tradução de shape: o backend `EmpresaOut` é snake (`toCamel` roda no
 * `fetchJson`), mas tem campos e domínios diferentes do `Empresa` do front:
 *   - `regimeTributario` lowercase (`simples_nacional`) → enum UPPER do front.
 *   - `faturamento12m` string decimal (`"680000.00"`) → `number` no front
 *     (usado em estimativas RBT12; NÃO é caminho de precisão monetária).
 *   - sem `setor`/`socios`/`cnae`/`bancosConectados`/`modulosAtivos`/`criadoEm`
 *     no backend → derivados/defaults no mapper (gaps registrados no handoff).
 *
 * O lookup de CNPJ usa o endpoint de onboarding (que JÁ cria a empresa). O shape
 * de `OnboardingResultadoOut` é mais pobre que o `CnpjLookupResponse` do wizard
 * (sem endereço completo nem sócios) — mapeamos o que existe.
 */
import {
  cnpjLookupResponseSchema,
  type CnpjLookupResponse,
} from "@/lib/schemas/cnpj-lookup";
import {
  empresaSchema,
  type Empresa,
  type RegimeTributario,
  type SetorAtividade,
} from "@/lib/schemas/empresa";

import { fetchJson, toSnake } from "@/lib/http";
import { z } from "zod";

// ── Schema cru do backend (camelCase, pós-toCamel) ───────────────────────────

const empresaOutSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  cnpj: z.string(),
  razaoSocial: z.string(),
  nomeFantasia: z.string().nullable().optional(),
  regimeTributario: z.string(),
  perfilUi: z.string(),
  anexoSimples: z.string().nullable().optional(),
  cnaePrincipal: z.string().nullable().optional(),
  municipio: z.string().nullable().optional(),
  codigoMunicipioIbge: z.string().nullable().optional(),
  uf: z.string().nullable().optional(),
  faturamento12m: z.string().nullable().optional(), // decimal string
  ativa: z.boolean(),
  aliquotaIssValidada: z.boolean().optional(),
});
type EmpresaOut = z.infer<typeof empresaOutSchema>;

const empresaOutListSchema = z.array(empresaOutSchema);

const onboardingResultadoSchema = z.object({
  cnpj: z.string(),
  razaoSocial: z.string(),
  nomeFantasia: z.string().nullable().optional(),
  porte: z.string(),
  situacaoCadastral: z.string(),
  cnaePrincipal: z.string().nullable().optional(),
  cnaeDescricao: z.string().nullable().optional(),
  municipio: z.string().nullable().optional(),
  codigoMunicipioIbge: z.string().nullable().optional(),
  uf: z.string().nullable().optional(),
  regimeSugerido: z.string(),
  anexoSugerido: z.string().nullable().optional(),
  empresaCriada: empresaOutSchema.nullable().optional(),
  aviso: z.string().nullable().optional(),
});

// ── Mappers ──────────────────────────────────────────────────────────────────

const REGIME_BACK_TO_FRONT: Record<string, RegimeTributario> = {
  mei: "MEI",
  simples_nacional: "SIMPLES_NACIONAL",
  lucro_presumido: "LUCRO_PRESUMIDO",
  lucro_real: "LUCRO_REAL",
};

const REGIME_FRONT_TO_BACK: Record<RegimeTributario, string> = {
  MEI: "mei",
  SIMPLES_NACIONAL: "simples_nacional",
  LUCRO_PRESUMIDO: "lucro_presumido",
  LUCRO_REAL: "lucro_real",
};

function setorPorCnae(cnae: string): SetorAtividade {
  const grupo = cnae.slice(0, 2);
  if (grupo.startsWith("47")) return "COMERCIO";
  if (grupo.startsWith("10") || grupo.startsWith("20") || grupo.startsWith("30"))
    return "INDUSTRIA";
  return "SERVICOS";
}

function modulosPorRegime(r: RegimeTributario): string[] {
  const base = ["home", "fiscal", "agenda", "compliance", "configuracoes"];
  if (r === "MEI") return [...base, "notas"];
  return [
    ...base,
    "notas",
    "contabil",
    "controles",
    "pessoal",
    "relatorios",
    "assistente",
  ];
}

function paraNumero(s: string | null | undefined): number {
  if (!s) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

/**
 * `EmpresaOut` (backend) → `Empresa` (front). Campos ausentes no backend
 * recebem default seguro (gaps registrados no handoff — NÃO inventamos dado).
 */
export function mapearEmpresa(out: EmpresaOut): Empresa {
  const regime = REGIME_BACK_TO_FRONT[out.regimeTributario] ?? "SIMPLES_NACIONAL";
  const cnae = out.cnaePrincipal ?? "";
  const candidate = {
    id: out.id,
    cnpj: out.cnpj,
    razaoSocial: out.razaoSocial,
    nomeFantasia: out.nomeFantasia ?? undefined,
    regime,
    anexoSimples:
      regime === "SIMPLES_NACIONAL" && out.anexoSimples
        ? out.anexoSimples
        : undefined,
    setor: setorPorCnae(cnae),
    cnae,
    uf: out.uf ?? "SP",
    municipio: out.municipio ?? "",
    inscricaoEstadual: undefined,
    inscricaoMunicipal: undefined,
    faturamento12m: paraNumero(out.faturamento12m),
    socios: [],
    certificadoA1: undefined,
    bancosConectados: [],
    modulosAtivos: modulosPorRegime(regime),
    criadoEm: new Date().toISOString(),
    perfilUi: out.perfilUi,
    codigoMunicipioIbge: out.codigoMunicipioIbge ?? undefined,
    ativa: out.ativa,
    aliquotaIssValidada: out.aliquotaIssValidada,
  };
  return empresaSchema.parse(candidate);
}

/** `OnboardingResultadoOut` → `CnpjLookupResponse` (shape do wizard). */
function mapearLookup(
  r: z.infer<typeof onboardingResultadoSchema>
): CnpjLookupResponse {
  const situacaoUpper = (r.situacaoCadastral ?? "").toUpperCase();
  const situacao = (["ATIVA", "BAIXADA", "INAPTA", "SUSPENSA"] as const).includes(
    situacaoUpper as never
  )
    ? (situacaoUpper as "ATIVA" | "BAIXADA" | "INAPTA" | "SUSPENSA")
    : "ATIVA";

  const candidate = {
    cnpj: r.cnpj,
    razaoSocial: r.razaoSocial,
    nomeFantasia: r.nomeFantasia ?? "",
    cnaePrincipal: {
      codigo: r.cnaePrincipal ?? "",
      descricao: r.cnaeDescricao ?? "",
    },
    // Gap: backend não retorna CNAEs secundários nem endereço completo.
    cnaesSecundarios: [],
    endereco: {
      logradouro: "",
      numero: "",
      bairro: "",
      municipio: r.municipio ?? "",
      uf: r.uf ?? "SP",
      cep: "",
    },
    porte: r.porte,
    situacao,
    dataAbertura: "",
    // Gap: backend não retorna quadro societário no onboarding.
    socios: [],
  };
  return cnpjLookupResponseSchema.parse(candidate);
}

// ── API pública ──────────────────────────────────────────────────────────────

export interface CriarEmpresaInput {
  cnpj: string;
  razaoSocial: string;
  nomeFantasia?: string;
  regime: RegimeTributario;
  anexoSimples?: string;
  cnaePrincipal?: string;
  municipio?: string;
  codigoMunicipioIbge?: string;
  uf?: string;
  faturamento12m?: number;
}

/**
 * Campos editáveis de `PUT /v1/empresas/{id}`. Semântica de PUT parcial:
 * `undefined` = "não gerencio este campo" → NÃO é enviado (o backend
 * `exclude_unset` preserva o valor atual); `null` = "limpar"; valor = "definir".
 * Isso evita zerar dado-mestre (ex.: `cnaePrincipal`) que o form não edita.
 */
export interface AtualizarEmpresaInput {
  razaoSocial?: string;
  nomeFantasia?: string | null;
  regime?: RegimeTributario;
  anexoSimples?: string | null;
  cnaePrincipal?: string | null;
  municipio?: string;
  codigoMunicipioIbge?: string | null;
  uf?: string;
  inscricaoEstadual?: string | null;
  inscricaoMunicipal?: string | null;
  faturamento12m?: number;
}

export const empresa = {
  /** `GET /v1/empresas` → lista de empresas do tenant (RLS via JWT). */
  listar: async (): Promise<Empresa[]> => {
    const out = await fetchJson("/empresas", empresaOutListSchema);
    return out.map(mapearEmpresa);
  },

  /** `GET /v1/empresas/{id}`. */
  obter: async (id: string): Promise<Empresa> => {
    const out = await fetchJson(`/empresas/${id}`, empresaOutSchema);
    return mapearEmpresa(out);
  },

  /** `POST /v1/empresas` → cria empresa (EmpresaIn). */
  criar: async (input: CriarEmpresaInput): Promise<Empresa> => {
    const body = {
      // `toSnake` converte camel→snake, MAS só insere `_` antes de LETRAS
      // maiúsculas — não antes de dígitos. `faturamento12m` ficaria igual e o
      // EmpresaIn (extra="forbid") devolveria 422; por isso a chave de dinheiro
      // é montada à mão como `faturamento_12m`.
      ...(toSnake({
        cnpj: input.cnpj,
        razaoSocial: input.razaoSocial,
        nomeFantasia: input.nomeFantasia ?? null,
        regimeTributario: REGIME_FRONT_TO_BACK[input.regime],
        anexoSimples: input.anexoSimples ?? null,
        cnaePrincipal: input.cnaePrincipal ?? null,
        municipio: input.municipio ?? null,
        codigoMunicipioIbge: input.codigoMunicipioIbge ?? null,
        uf: input.uf ?? null,
      }) as Record<string, unknown>),
      // Dinheiro como string decimal (nunca float no body).
      faturamento_12m:
        input.faturamento12m != null ? String(input.faturamento12m) : null,
    };
    const out = await fetchJson("/empresas", empresaOutSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return mapearEmpresa(out);
  },

  /**
   * `PUT /v1/empresas/{id}` → atualiza o cadastro (EmpresaUpdateIn → EmpresaOut).
   *
   * PUT PARCIAL: só envia as chaves que o caller forneceu (≠ `undefined`).
   * Chaves omitidas são preservadas pelo backend (`model_dump(exclude_unset)`).
   * Isto é CRÍTICO: mandar `cnae_principal: null` por engano (campo que o form
   * não edita) zerava o CNAE da empresa a cada save — não enviar a chave evita.
   * Body em snake_case explícito porque IE/IM viram `ie`/`im` (não é conversão
   * camel→snake direta). O `EmpresaOut` não ecoa IE/IM — o caller os preserva.
   */
  atualizar: async (id: string, input: AtualizarEmpresaInput): Promise<Empresa> => {
    const body: Record<string, string | null> = {};
    // `undefined` → omite (preserva no backend); `null` → limpa; valor → define.
    const definir = (chave: string, valor: string | null | undefined): void => {
      if (valor !== undefined) body[chave] = valor;
    };
    definir("razao_social", input.razaoSocial);
    definir("nome_fantasia", input.nomeFantasia);
    definir(
      "regime_tributario",
      input.regime ? REGIME_FRONT_TO_BACK[input.regime] : undefined
    );
    definir("anexo_simples", input.anexoSimples);
    definir("cnae_principal", input.cnaePrincipal);
    definir("municipio", input.municipio);
    definir("codigo_municipio_ibge", input.codigoMunicipioIbge);
    definir("uf", input.uf);
    definir("ie", input.inscricaoEstadual);
    definir("im", input.inscricaoMunicipal);
    // Dinheiro como string decimal (nunca float no body).
    definir(
      "faturamento_12m",
      input.faturamento12m != null ? String(input.faturamento12m) : undefined
    );
    const out = await fetchJson(`/empresas/${id}`, empresaOutSchema, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return mapearEmpresa(out);
  },

  /**
   * `POST /v1/empresas/onboarding` → consulta BrasilAPI e JÁ CRIA a empresa.
   * Devolve o shape `CnpjLookupResponse` que o wizard consome. A empresa criada
   * (quando houver) é exposta via `lookupCnpjComEmpresa` abaixo.
   */
  lookupCnpj: async (cnpj: string): Promise<CnpjLookupResponse> => {
    const r = await empresa.lookupCnpjComEmpresa(cnpj);
    return r.dados;
  },

  /**
   * Variante que devolve também a `Empresa` criada pelo onboarding (o backend
   * cria automaticamente). O wizard usa para pular a criação manual.
   */
  lookupCnpjComEmpresa: async (
    cnpj: string
  ): Promise<{ dados: CnpjLookupResponse; empresa: Empresa | null }> => {
    // O endpoint /empresas/onboarding aceita SÓ `cnpj` (schema com extra="forbid").
    // Enviar `faturamento12m` (mesmo null) dava 422 extra_forbidden e quebrava o
    // onboarding inteiro de contas novas. O faturamento é refinado depois.
    const body = toSnake({ cnpj });
    const r = await fetchJson("/empresas/onboarding", onboardingResultadoSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return {
      dados: mapearLookup(r),
      empresa: r.empresaCriada ? mapearEmpresa(r.empresaCriada) : null,
    };
  },
};
