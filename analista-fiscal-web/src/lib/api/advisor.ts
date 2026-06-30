/**
 * Adapter de domínio: CONSULTOR (advisor).
 *
 * Liga a tela do consultor proativo ao módulo backend `advisor`
 * (8 endpoints reais, base `/v1`, sempre RLS por empresa):
 *
 *   1. GET  /v1/empresas/{id}/advisor/anomalias?limit          → alertas abertos
 *   2. POST /v1/empresas/{id}/advisor/anomalias/{aid}/dispensar → dispensa (201/409)
 *   3. GET  /v1/empresas/{id}/advisor/sugestoes                 → oportunidades
 *   4. POST /v1/empresas/{id}/advisor/digest                    → gera resumo semanal
 *   5. GET  /v1/empresas/{id}/advisor/digests                   → lista resumos
 *   6. GET  /v1/empresas/{id}/advisor/digests/{did}             → detalhe de um resumo
 *   7. POST /v1/empresas/{id}/advisor/digests/{did}/enviar      → envia via WhatsApp
 *
 * O consultor é a "camada 1" determinística: detecta anomalias (z-score/IQR),
 * sugere otimizações (Fator R, parcelamento) e redige um digest semanal. O
 * usuário PME vê linguagem amigável — os enums crus (`das`, `zscore`,
 * `informativa`) são traduzidos na camada de UI, nunca expostos.
 *
 * Invariantes (ver `manifestacao.ts` › mesmo contrato):
 *  - Token via header (injetado por `fetchJson`); `empresa_id` na rota.
 *  - Dinheiro/decimais (`valorObservado`, `economiaAnualEstimada`, `zScore`…)
 *    preservados como STRING decimal — NUNCA float.
 */
import { z } from "zod";

import { ApiError, fetchJson, toSnake } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";

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

// ── shapes REAIS do backend (camelCase, pós-`toCamel`) ───────────────────────
//
// Enums ficam como `z.string()` (tolerância a valores novos do backend); a
// tradução para rótulo/cor acontece na UI com fallback — espelha o critério já
// adotado em `manifestacao.ts` (`tipoEvento`/`status` como string).

/** `AnomaliaOut` — salto atípico numa apuração (z-score/IQR). */
export const anomaliaSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipo: z.string(), // das | irpj | csll | pis | cofins | iss | icms
  competencia: z.string(), // date (YYYY-MM-DD)
  severidade: z.string(), // baixa | media | alta
  valorObservado: z.string(), // decimal string — NUNCA float
  valorEsperado: z.string(),
  zScore: z.string(),
  deltaPercentual: z.string(),
  metodo: z.string(), // zscore | iqr
  amostraN: z.number(),
  mensagem: z.string(),
  algoritmoVersao: z.string(),
  detectadoEm: z.string(),
  dispensadaEm: z.string().nullable(),
  dispensadaPor: z.string().nullable(),
  motivoDispensa: z.string().nullable(),
});
export type Anomalia = z.infer<typeof anomaliaSchema>;

/** `SugestaoOut` — oportunidade de otimização (Fator R, parcelamento…). */
export const sugestaoSchema = z.object({
  codigo: z.string(),
  titulo: z.string(),
  descricao: z.string(),
  severidade: z.string(), // informativa | media | alta
  economiaAnualEstimada: z.string().nullable(), // decimal string | null
  fonteNorma: z.string(),
  detalhes: z.record(z.string(), z.string()),
  observacaoEstimativa: z.string(),
  algoritmoVersao: z.string(),
});
export type Sugestao = z.infer<typeof sugestaoSchema>;

/** `ListaSugestoesOut`. */
export const listaSugestoesSchema = z.object({
  competenciaReferencia: z.string(),
  total: z.number(),
  sugestoes: z.array(sugestaoSchema),
});
export type ListaSugestoes = z.infer<typeof listaSugestoesSchema>;

/** `DigestOut` — resumo semanal redigido (template ou LLM). */
export const digestSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  semanaIso: z.string(), // "2026-W27"
  periodoInicio: z.string(),
  periodoFim: z.string(),
  textoRedigido: z.string(),
  fonteRedacao: z.string(), // template | llm_gemini_flash | llm_fallback
  citacoes: z.array(z.string()),
  status: z.string(), // preparado | enviado | cancelado | falhou
  llmProvider: z.string().nullable(),
  custoUsd: z.string().nullable(),
  tokensInput: z.number().nullable(),
  tokensOutput: z.number().nullable(),
  tentativasEnvio: z.number(),
  ultimoErroEnvio: z.string().nullable(),
  enviadoViaWhatsappEm: z.string().nullable(),
  enviadoTemplateName: z.string().nullable(),
  algoritmoVersao: z.string(),
  criadoEm: z.string(),
});
export type Digest = z.infer<typeof digestSchema>;

/** `ListaDigestsOut`. */
export const listaDigestsSchema = z.object({
  total: z.number(),
  digests: z.array(digestSchema),
});
export type ListaDigests = z.infer<typeof listaDigestsSchema>;

// ── entradas de mutação ───────────────────────────────────────────────────────

export interface GerarDigestInput {
  /** `true` regera e supersede o anterior (idempotência → 409 se já existe). */
  forcar?: boolean;
  /** `true` habilita redação por Gemini Flash; default = template determinístico. */
  usarLlm?: boolean;
}

// ── superfície pública ────────────────────────────────────────────────────────

export const advisor = {
  /** Lista os alertas (anomalias) abertos — mais recentes primeiro. */
  listarAnomalias: (opts?: { limit?: number }): Promise<Anomalia[]> => {
    const qs = new URLSearchParams();
    if (opts?.limit !== undefined) qs.set("limit", String(opts.limit));
    const sufixo = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson(
      rotaEmpresa(`/advisor/anomalias${sufixo}`),
      z.array(anomaliaSchema)
    );
  },

  /** Dispensa um alerta com motivo (idempotente: 409 se já dispensado). */
  dispensarAnomalia: (
    anomaliaId: string,
    motivo: string
  ): Promise<Anomalia> =>
    fetchJson(
      rotaEmpresa(`/advisor/anomalias/${anomaliaId}/dispensar`),
      anomaliaSchema,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toSnake({ motivo })),
      }
    ),

  /** Lista as oportunidades de otimização da competência atual. */
  listarSugestoes: (): Promise<ListaSugestoes> =>
    fetchJson(rotaEmpresa("/advisor/sugestoes"), listaSugestoesSchema),

  /** Gera o resumo semanal (template por default; LLM opt-in). */
  gerarDigest: (input?: GerarDigestInput): Promise<Digest> =>
    fetchJson(rotaEmpresa("/advisor/digest"), digestSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        toSnake({
          forcar: input?.forcar ?? false,
          usarLlm: input?.usarLlm ?? false,
        })
      ),
    }),

  /** Lista os resumos semanais já gerados (mais recentes primeiro). */
  listarDigests: (): Promise<ListaDigests> =>
    fetchJson(rotaEmpresa("/advisor/digests"), listaDigestsSchema),

  /** Detalhe de um resumo semanal específico. */
  obterDigest: (digestId: string): Promise<Digest> =>
    fetchJson(rotaEmpresa(`/advisor/digests/${digestId}`), digestSchema),

  /** Envia o resumo via WhatsApp (idempotente: 409 se já enviado). */
  enviarDigest: (digestId: string): Promise<Digest> =>
    fetchJson(
      rotaEmpresa(`/advisor/digests/${digestId}/enviar`),
      digestSchema,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    ),
};
