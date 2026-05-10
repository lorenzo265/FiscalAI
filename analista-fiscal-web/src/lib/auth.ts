const FLAG_LOGADO = "analista-fiscal:logado";
const FLAG_USER_EMAIL = "analista-fiscal:email";

export function isLogado(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(FLAG_LOGADO) === "1";
}

export function emailLogado(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(FLAG_USER_EMAIL);
}

export function entrar(email: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(FLAG_LOGADO, "1");
  localStorage.setItem(FLAG_USER_EMAIL, email);
}

export function sair(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(FLAG_LOGADO);
  localStorage.removeItem(FLAG_USER_EMAIL);
}
