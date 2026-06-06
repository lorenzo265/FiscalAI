/**
 * Store da empresa ativa (Fase A — Fundação).
 *
 * Os adapters de domínio montam rotas `/v1/empresas/{empresa_id}/…` a partir
 * do `empresa_id` (UUID) da empresa selecionada. Aqui entregamos apenas o
 * util + store em `localStorage` (chave `arkan:empresa-id`). A população real
 * (seletor de empresa + provider) vem na Fase B.
 */

const KEY_EMPRESA_ID = "arkan:empresa-id";

function temWindow(): boolean {
  return typeof window !== "undefined";
}

/** UUID da empresa ativa, ou `null` se nenhuma selecionada. */
export function getEmpresaIdAtiva(): string | null {
  if (!temWindow()) return null;
  return localStorage.getItem(KEY_EMPRESA_ID);
}

/** Define (ou limpa, com `null`) a empresa ativa. */
export function setEmpresaIdAtiva(id: string | null): void {
  if (!temWindow()) return;
  if (id) {
    localStorage.setItem(KEY_EMPRESA_ID, id);
  } else {
    localStorage.removeItem(KEY_EMPRESA_ID);
  }
}
