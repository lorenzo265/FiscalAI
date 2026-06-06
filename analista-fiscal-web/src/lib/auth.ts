/**
 * Token store real (Fase A — Fundação).
 *
 * Guarda o JWT emitido pelo backend (`POST /v1/auth/login|register`) em
 * `localStorage`, com expiração. Substitui o mock de flag booleana, mas
 * PRESERVA a superfície pública já consumida pelo app:
 *   - `isLogado()`   → existe token não-expirado.
 *   - `emailLogado()`→ email da sessão (quando informado).
 *   - `entrar(email)`→ compat: marca sessão (UI real de login vem na Fase B).
 *   - `sair()`       → limpa a sessão.
 *
 * Novidades desta fase (consumidas por `http.ts` e pela Fase B):
 *   - `getToken()`, `setSessao(...)`, `limparSessao()`.
 *
 * Chaves: `arkan:token`, `arkan:token-exp`, `arkan:email`.
 */

const KEY_TOKEN = "arkan:token";
const KEY_EXPIRY = "arkan:token-exp"; // epoch ms
const KEY_EMAIL = "arkan:email";

export interface SessaoInput {
  access_token: string;
  /** TTL em segundos (campo `expires_in` do backend). */
  expires_in: number;
  email?: string;
}

function temWindow(): boolean {
  return typeof window !== "undefined";
}

/** Token JWT corrente, ou `null` se ausente/expirado. */
export function getToken(): string | null {
  if (!temWindow()) return null;
  const token = localStorage.getItem(KEY_TOKEN);
  if (!token) return null;
  const expRaw = localStorage.getItem(KEY_EXPIRY);
  if (expRaw) {
    const exp = Number(expRaw);
    if (Number.isFinite(exp) && Date.now() >= exp) {
      limparSessao();
      return null;
    }
  }
  return token;
}

/** Persiste a sessão emitida pelo backend (token + expiry + email opcional). */
export function setSessao(input: SessaoInput): void {
  if (!temWindow()) return;
  localStorage.setItem(KEY_TOKEN, input.access_token);
  const expMs = Date.now() + Math.max(0, input.expires_in) * 1000;
  localStorage.setItem(KEY_EXPIRY, String(expMs));
  if (input.email) {
    localStorage.setItem(KEY_EMAIL, input.email);
  }
}

/** Limpa toda a sessão (token + expiry + email). */
export function limparSessao(): void {
  if (!temWindow()) return;
  localStorage.removeItem(KEY_TOKEN);
  localStorage.removeItem(KEY_EXPIRY);
  localStorage.removeItem(KEY_EMAIL);
}

// ── Superfície legada preservada ─────────────────────────────────────────────

/** True quando há token válido (não-expirado). */
export function isLogado(): boolean {
  return getToken() !== null;
}

/** Email da sessão corrente, ou `null`. */
export function emailLogado(): string | null {
  if (!temWindow()) return null;
  return localStorage.getItem(KEY_EMAIL);
}

/**
 * Compat com a UI de login atual (mock). A UI real (RHF+Zod) que chama o
 * backend e usa `setSessao` chega na Fase B. Aqui registramos um token
 * placeholder de sessão local para não quebrar o fluxo de demonstração: o
 * `auth-guard` e `isLogado` continuam funcionando.
 */
export function entrar(email: string): void {
  if (!temWindow()) return;
  setSessao({
    access_token: localStorage.getItem(KEY_TOKEN) ?? "dev-session",
    expires_in: 60 * 60, // 1h, alinhado ao JWT_EXPIRE_MINUTES default do backend
    email,
  });
}

/** Encerra a sessão. */
export function sair(): void {
  limparSessao();
}
