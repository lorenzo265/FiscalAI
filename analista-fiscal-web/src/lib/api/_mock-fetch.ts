/**
 * Helper interno do split de `api-client.ts` (Fase A — Fundação).
 *
 * Preserva EXATAMENTE o `fetchJson` mock original (BASE="/api/mock"), usado
 * pelos domínios `empresa`, `fiscal`, `agenda`, `notas` enquanto ainda
 * apontam para os Route Handlers mock. NÃO muda comportamento nesta fase.
 *
 * Quando cada agente de domínio reescrever `src/lib/api/<dominio>.ts` para
 * falar com o backend real, troca este import por `fetchJson` de
 * `@/lib/http`. A `ApiError` já é a real (`@/lib/http`).
 */
import { z } from "zod";

import { ApiError } from "@/lib/http";

const MOCK_BASE = "/api/mock";

export async function mockFetchJson<T>(
  path: string,
  schema: z.ZodSchema<T>,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${MOCK_BASE}${path}`, init);
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, "RespostaInvalida", "invalid_json");
  }
  if (!res.ok) {
    const errMsg =
      (parsed as { error?: string } | null)?.error ?? `http_${res.status}`;
    throw new ApiError(res.status, errMsg, errMsg);
  }
  return schema.parse(parsed);
}

export function querystringDe(
  empresa: import("@/lib/schemas/empresa").Empresa | null | undefined
): string {
  if (!empresa) return "";
  const sp = new URLSearchParams({
    cnpj: empresa.cnpj,
    razao: empresa.razaoSocial,
    regime: empresa.regime,
    fat12: String(empresa.faturamento12m),
    uf: empresa.uf,
  });
  if (empresa.anexoSimples) sp.set("anexo", empresa.anexoSimples);
  return `?${sp.toString()}`;
}
