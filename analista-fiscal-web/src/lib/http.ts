/**
 * Cliente HTTP real (Fase A — Fundação da integração front↔back).
 *
 * Substitui o `fetchJson` mock de `api-client.ts`. Fala com o backend FastAPI
 * (`NEXT_PUBLIC_API_BASE_URL`), injeta o JWT do token store, traduz
 * snake_case (backend) ↔ camelCase (schemas Zod do front) e mapeia o erro de
 * domínio `{codigo, mensagem}` para `ApiError`.
 *
 * Contrato (ver `hadoff-front-back.md` › Apêndice de Contrato):
 *  - Base URL: `process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1"`.
 *  - Auth: header `Authorization: Bearer <token>` quando há sessão.
 *  - Tenant via JWT (nunca querystring); `empresa_id` vai na rota.
 *  - Dinheiro = string decimal — `toCamel`/`toSnake` NUNCA convertem números.
 *  - 401 → limpa sessão + redireciona para `/login`.
 */
import { z } from "zod";

import { getToken, limparSessao } from "@/lib/auth";

export const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/**
 * Erro de domínio/HTTP do backend.
 *
 * Compatibilidade: telas existentes leem `.status` e `.message`. Esta fase
 * acrescenta `.codigo` e `.mensagem` (formato `{codigo, mensagem}` do FastAPI).
 * `message` recebe a `mensagem` quando disponível, senão um fallback técnico.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly codigo: string;
  readonly mensagem: string;

  constructor(status: number, codigo: string, mensagem: string) {
    // `message` preserva compat com `.message` lido pelas telas.
    super(mensagem || codigo || `http_${status}`);
    this.name = "ApiError";
    this.status = status;
    this.codigo = codigo;
    this.mensagem = mensagem || codigo || `http_${status}`;
  }
}

// ── snake ↔ camel (deep, preservando valores) ──────────────────────────────

function snakeToCamel(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase());
}

function camelToSnake(key: string): string {
  return key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

/**
 * Converte chaves snake_case → camelCase recursivamente (arrays + objetos
 * aninhados). Valores são preservados como estão — strings de dinheiro/decimais
 * continuam string; nada é convertido para `number`.
 */
export function toCamel(input: unknown): unknown {
  if (Array.isArray(input)) {
    return input.map((item) => toCamel(item));
  }
  if (isPlainObject(input)) {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      out[snakeToCamel(key)] = toCamel(value);
    }
    return out;
  }
  return input;
}

/**
 * Converte chaves camelCase → snake_case recursivamente. Espelho de `toCamel`.
 * Valores preservados — dinheiro como string permanece string.
 */
export function toSnake(input: unknown): unknown {
  if (Array.isArray(input)) {
    return input.map((item) => toSnake(item));
  }
  if (isPlainObject(input)) {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      out[camelToSnake(key)] = toSnake(value);
    }
    return out;
  }
  return input;
}

// ── 401 handler ────────────────────────────────────────────────────────────

function handle401(): void {
  limparSessao();
  if (typeof window !== "undefined") {
    window.location.assign("/login");
  }
}

// ── fetchJson ──────────────────────────────────────────────────────────────

/**
 * Faz a requisição, valida a resposta com Zod e devolve `T`.
 *
 * Mesma assinatura do `fetchJson` do api-client mock: `(path, schema, init?)`.
 * Monta `BASE + path`, injeta o token, aplica `toCamel` na resposta antes de
 * validar (backend é snake_case, schemas são camelCase) e levanta `ApiError`
 * com `{codigo, mensagem}` em caso de erro.
 */
export async function fetchJson<T>(
  path: string,
  schema: z.ZodSchema<T>,
  init?: RequestInit
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch (err) {
    throw new ApiError(
      0,
      "FalhaDeRede",
      err instanceof Error ? err.message : "Falha de rede ao contatar a API"
    );
  }

  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, "RespostaInvalida", "invalid_json");
  }

  if (!res.ok) {
    if (res.status === 401) {
      handle401();
    }
    const body = parsed as
      | { codigo?: string; mensagem?: string; detail?: unknown; error?: string }
      | null;
    const codigo =
      body?.codigo ?? body?.error ?? `http_${res.status}`;
    const mensagem =
      body?.mensagem ??
      (typeof body?.detail === "string" ? body.detail : undefined) ??
      body?.error ??
      `http_${res.status}`;
    throw new ApiError(res.status, codigo, mensagem);
  }

  return schema.parse(toCamel(parsed));
}
