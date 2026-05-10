import { apenasDigitos } from "./cnpj";

export function formatarCPF(cpf: string): string {
  const d = apenasDigitos(cpf).padStart(11, "0").slice(-11);
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9, 11)}`;
}

export function mascaraCPF(input: string): string {
  const d = apenasDigitos(input).slice(0, 11);
  let out = "";
  for (let i = 0; i < d.length; i++) {
    if (i === 3 || i === 6) out += ".";
    if (i === 9) out += "-";
    out += d[i];
  }
  return out;
}

export function validarCPF(cpf: string): boolean {
  const d = apenasDigitos(cpf);
  if (d.length !== 11) return false;
  if (/^(\d)\1{10}$/.test(d)) return false;

  const calc = (slice: string, factor: number): number => {
    let sum = 0;
    for (let i = 0; i < slice.length; i++) {
      sum += Number(slice[i]) * (factor - i);
    }
    const mod = (sum * 10) % 11;
    return mod === 10 ? 0 : mod;
  };

  const d1 = calc(d.slice(0, 9), 10);
  const d2 = calc(d.slice(0, 10), 11);
  return Number(d[9]) === d1 && Number(d[10]) === d2;
}
