/**
 * Adapter de domínio: auth (Fase B — Auth & Empresa).
 *
 * Fala com o backend real de autenticação. ATENÇÃO: o router de auth do backend
 * é montado SEM o prefixo `/v1` (`/auth/login`, `/auth/register`) — diferente
 * dos demais domínios, que vivem sob `/v1/empresas/...`. Como `BASE` termina em
 * `/v1`, montamos a URL de auth a partir da RAIZ do host (BASE sem o `/v1`).
 *
 * Não usa `fetchJson` (que prefixa `BASE` e injeta token): login/register são
 * públicos e moram fora de `/v1`. Reaproveita `ApiError`, `toCamel` e a mesma
 * semântica de parsing de erro `{codigo, mensagem}` do backend.
 */
import { z } from "zod";

import { ApiError, BASE, toCamel } from "@/lib/http";

/** Raiz do host (BASE sem o segmento `/v1`), para os endpoints `/auth/*`. */
function rootBase(): string {
  return BASE.replace(/\/v1\/?$/, "");
}

// ── Schemas (camelCase — backend é snake, toCamel roda antes do parse) ───────

export const tokenOutSchema = z.object({
  accessToken: z.string(),
  tokenType: z.string().optional(),
  expiresIn: z.number(),
});
export type TokenOut = z.infer<typeof tokenOutSchema>;

const usuarioOutSchema = z.object({
  id: z.string(),
  tenantId: z.string(),
  nome: z.string(),
  email: z.string(),
});

const tenantOutSchema = z.object({
  id: z.string(),
  nome: z.string(),
  slug: z.string(),
});

export const registerOutSchema = z.object({
  accessToken: z.string(),
  tokenType: z.string().optional(),
  expiresIn: z.number(),
  usuario: usuarioOutSchema,
  tenant: tenantOutSchema,
});
export type RegisterOut = z.infer<typeof registerOutSchema>;

export interface LoginInput {
  tenantSlug: string;
  email: string;
  senha: string;
}

export interface RegisterInput {
  tenantNome: string;
  tenantSlug: string;
  usuarioNome: string;
  usuarioEmail: string;
  usuarioSenha: string;
}

// ── fetch de auth (host root, sem token, sem `/v1`) ──────────────────────────

async function postAuth<T>(
  path: string,
  schema: z.ZodSchema<T>,
  body: unknown
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${rootBase()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
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
    const b = parsed as
      | { codigo?: string; mensagem?: string; detail?: unknown }
      | null;
    const codigo = b?.codigo ?? `http_${res.status}`;
    const mensagem =
      b?.mensagem ??
      (typeof b?.detail === "string" ? b.detail : undefined) ??
      `http_${res.status}`;
    throw new ApiError(res.status, codigo, mensagem);
  }

  return schema.parse(toCamel(parsed));
}

export const auth = {
  /** `POST /auth/login` → token. Backend exige `tenant_slug`. */
  login: (input: LoginInput): Promise<TokenOut> =>
    postAuth("/auth/login", tokenOutSchema, {
      tenant_slug: input.tenantSlug,
      email: input.email,
      senha: input.senha,
    }),

  /** `POST /auth/register` → token + usuário + tenant (cria tenant + admin). */
  register: (input: RegisterInput): Promise<RegisterOut> =>
    postAuth("/auth/register", registerOutSchema, {
      tenant_nome: input.tenantNome,
      tenant_slug: input.tenantSlug,
      usuario_nome: input.usuarioNome,
      usuario_email: input.usuarioEmail,
      usuario_senha: input.usuarioSenha,
    }),
};

/**
 * Traduz códigos de erro de auth do backend para mensagem amigável (nunca
 * vazar o `codigo` cru ao usuário).
 */
export function mensagemAmigavelAuth(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.codigo) {
      case "CredenciaisInvalidas":
      case "TokenInvalido":
        return "Email ou senha incorretos. Confira e tente novamente.";
      case "TenantNaoEncontrado":
        return "Código da conta não encontrado. Confira o código informado.";
      case "SlugJaCadastrado":
        return "Já existe uma conta com esse código. Escolha outro.";
      case "EmailJaCadastrado":
        return "Esse email já está cadastrado nesta conta.";
      case "FalhaDeRede":
        return "Não conseguimos contatar o servidor. Verifique sua conexão.";
      default:
        if (err.status === 422) {
          return "Confira os dados informados e tente novamente.";
        }
        return "Não foi possível concluir. Tente novamente em instantes.";
    }
  }
  return "Erro inesperado. Tente novamente.";
}
