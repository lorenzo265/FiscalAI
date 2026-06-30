/**
 * Adapter de domínio: MANIFESTAÇÃO DO DESTINATÁRIO (MD-e).
 *
 * Liga a tela de notas recebidas ao módulo backend `manifestacao`
 * (4 endpoints reais, base `/v1`):
 *
 *   1. POST /v1/empresas/{id}/manifestacao              → registrar evento (201)
 *   2. GET  /v1/empresas/{id}/manifestacao              → listar eventos
 *   3. POST /v1/empresas/{id}/manifestacao/sincronizar  → DistribuiçãoDFe
 *   4. GET  /v1/empresas/{id}/manifestacao/destinadas   → NF-e descobertas
 *
 * Os 4 tipos de evento MD-e (SEFAZ): a tela usa nomes amigáveis
 * (`StatusManifesto`); o backend usa o código numérico (`tipo_evento`).
 * `STATUS_PARA_TIPO_EVENTO` traduz — o usuário PME nunca vê o código cru.
 *
 * Invariantes (ver `hadoff-front-back.md` › Apêndice):
 *  - Token via header (injetado por `fetchJson`); `empresa_id` na rota.
 *  - Dinheiro (`valor_total`) preservado como STRING decimal — NUNCA float.
 */
import { z } from "zod";

import { ApiError, fetchJson, toSnake } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import type { StatusManifesto } from "@/lib/schemas/nota";

// ── helper de rota ───────────────────────────────────────────────────────────

function rotaEmpresa(sufixo: string): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      0,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada. Entre na conta e escolha uma empresa."
    );
  }
  return `/empresas/${id}${sufixo}`;
}

// ── tipos de evento MD-e (código SEFAZ por nome amigável do front) ────────────

/** Os 4 manifestos efetivos (exclui o estado inicial `pendente_manifesto`). */
export type ManifestoEnviavel = Exclude<StatusManifesto, "pendente_manifesto">;

/** Código `tpEvento` do leiaute MD-e (NT 2014.002) por nome amigável. */
export const STATUS_PARA_TIPO_EVENTO: Record<
  ManifestoEnviavel,
  "210200" | "210210" | "210220" | "210240"
> = {
  confirmada: "210200",
  ciencia: "210210",
  desconhecida: "210220",
  nao_realizada: "210240",
};

// ── shapes REAIS do backend (camelCase, pós-`toCamel`) ───────────────────────

/** `ManifestacaoNFeOut` do backend (`app/modules/manifestacao/schemas.py`). */
export const manifestacaoOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  chaveNfe: z.string(),
  cnpjDestinatario: z.string(),
  tipoEvento: z.string(),
  sequencial: z.number(),
  justificativa: z.string().nullable(),
  status: z.string(),
  protocolo: z.string().nullable(),
  codigoStatusSefaz: z.number().nullable(),
  motivoSefaz: z.string().nullable(),
  xmlEventoStorageKey: z.string().nullable(),
  algoritmoVersao: z.string(),
  criadoEm: z.string(),
  assinadoEm: z.string().nullable(),
  transmitidoEm: z.string().nullable(),
  respondidoEm: z.string().nullable(),
});
export type ManifestacaoOut = z.infer<typeof manifestacaoOutSchema>;

/** `NfeDestinadaOut` — NF-e descoberta pelo DistribuiçãoDFe. */
export const nfeDestinadaSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  chaveNfe: z.string(),
  nsu: z.number(),
  emitenteCnpj: z.string().nullable(),
  emitenteNome: z.string().nullable(),
  valorTotal: z.string().nullable(), // decimal string — NUNCA float
  dhEmissao: z.string().nullable(),
  tipoDocumento: z.string(), // 'resumo' | 'completo'
  temXmlCompleto: z.boolean(),
  xmlStorageKey: z.string().nullable(),
  criadoEm: z.string(),
  atualizadoEm: z.string(),
});
export type NfeDestinada = z.infer<typeof nfeDestinadaSchema>;

/** `SincronizacaoResultadoOut` — eco de uma sincronização DistribuiçãoDFe. */
export const sincronizacaoResultadoSchema = z.object({
  novos: z.number(),
  atualizados: z.number(),
  ultNsu: z.number(),
  maxNsu: z.number(),
  truncado: z.boolean(),
});
export type SincronizacaoResultado = z.infer<
  typeof sincronizacaoResultadoSchema
>;

// ── entrada de registro ──────────────────────────────────────────────────────

export interface RegistrarManifestoInput {
  /** Chave de acesso da NF-e (44 dígitos). */
  chaveNfe: string;
  /** CNPJ da empresa que manifesta (14 dígitos, sem máscara). */
  cnpjDestinatario: string;
  /** Nome amigável; traduzido para o código `tpEvento` no adapter. */
  manifesto: ManifestoEnviavel;
  /** Obrigatória APENAS para "nao_realizada" (210240), 15–255 chars. */
  justificativa?: string;
}

// ── superfície pública ────────────────────────────────────────────────────────

export const manifestacao = {
  /** Registra um evento de manifestação do destinatário (POST, 201). */
  registrar: (input: RegistrarManifestoInput): Promise<ManifestacaoOut> => {
    const corpo: Record<string, string> = {
      chaveNfe: input.chaveNfe,
      cnpjDestinatario: input.cnpjDestinatario.replace(/\D/g, ""),
      tipoEvento: STATUS_PARA_TIPO_EVENTO[input.manifesto],
    };
    if (input.justificativa) corpo.justificativa = input.justificativa;
    return fetchJson(rotaEmpresa("/manifestacao"), manifestacaoOutSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toSnake(corpo)),
    });
  },

  /** Lista os eventos de manifestação já registrados da empresa. */
  listar: (): Promise<ManifestacaoOut[]> =>
    fetchJson(rotaEmpresa("/manifestacao"), z.array(manifestacaoOutSchema)),

  /** Dispara a sincronização DistribuiçãoDFe (descobre NF-e destinadas). */
  sincronizar: (): Promise<SincronizacaoResultado> =>
    fetchJson(
      rotaEmpresa("/manifestacao/sincronizar"),
      sincronizacaoResultadoSchema,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    ),

  /** Lista as NF-e destinadas descobertas (opcional: só pendentes de manifesto). */
  listarDestinadas: (opts?: {
    pendentes?: boolean;
  }): Promise<NfeDestinada[]> => {
    const qs = new URLSearchParams();
    if (opts?.pendentes !== undefined) {
      qs.set("pendentes", String(opts.pendentes));
    }
    const sufixo = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson(
      rotaEmpresa(`/manifestacao/destinadas${sufixo}`),
      z.array(nfeDestinadaSchema)
    );
  },
};
