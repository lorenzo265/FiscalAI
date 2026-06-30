"use client";

/**
 * Hooks do CONSULTOR (advisor) — fala com o backend real via `@/lib/api/advisor`.
 *
 * Três features: alertas (anomalias), oportunidades (sugestões) e resumo
 * semanal (digests). Leituras via `useQuery` (chave por empresa); mutações via
 * `useMutation` invalidando o cache do consultor.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { advisor, type GerarDigestInput } from "@/lib/api/advisor";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

// ── alertas (anomalias) ───────────────────────────────────────────────────────

/** Alertas abertos (saltos atípicos em apuração), mais recentes primeiro. */
export function useAnomalias(limit?: number) {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["advisor", "anomalias", empresa?.cnpj, limit ?? null],
    queryFn: () => advisor.listarAnomalias(limit ? { limit } : undefined),
    enabled: !!empresa,
  });
}

/** Dispensa um alerta com motivo (idempotente: 409 se já dispensado). */
export function useDispensarAnomalia() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      anomaliaId,
      motivo,
    }: {
      anomaliaId: string;
      motivo: string;
    }) => advisor.dispensarAnomalia(anomaliaId, motivo),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["advisor", "anomalias"] });
    },
  });
}

// ── oportunidades (sugestões) ─────────────────────────────────────────────────

/** Oportunidades de otimização da competência atual (Fator R, parcelamento…). */
export function useSugestoes() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["advisor", "sugestoes", empresa?.cnpj],
    queryFn: () => advisor.listarSugestoes(),
    enabled: !!empresa,
  });
}

// ── resumo semanal (digests) ──────────────────────────────────────────────────

/** Lista os resumos semanais já gerados (mais recentes primeiro). */
export function useDigests() {
  const { empresa } = useEmpresaAtual();
  return useQuery({
    queryKey: ["advisor", "digests", empresa?.cnpj],
    queryFn: () => advisor.listarDigests(),
    enabled: !!empresa,
  });
}

/** Gera o resumo semanal (template por default; LLM opt-in). */
export function useGerarDigest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input?: GerarDigestInput) => advisor.gerarDigest(input),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["advisor", "digests"] });
    },
  });
}

/** Envia um resumo via WhatsApp (idempotente: 409 se já enviado). */
export function useEnviarDigest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (digestId: string) => advisor.enviarDigest(digestId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["advisor", "digests"] });
    },
  });
}
