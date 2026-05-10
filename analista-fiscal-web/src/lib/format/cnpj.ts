export function apenasDigitos(str: string): string {
  return (str ?? "").replace(/\D+/g, "");
}

export function formatarCNPJ(cnpj: string): string {
  const d = apenasDigitos(cnpj).padStart(14, "0").slice(-14);
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12, 14)}`;
}

export function mascaraCNPJ(input: string): string {
  const d = apenasDigitos(input).slice(0, 14);
  let out = "";
  for (let i = 0; i < d.length; i++) {
    if (i === 2 || i === 5) out += ".";
    if (i === 8) out += "/";
    if (i === 12) out += "-";
    out += d[i];
  }
  return out;
}

export function validarCNPJ(cnpj: string): boolean {
  const d = apenasDigitos(cnpj);
  if (d.length !== 14) return false;
  if (/^(\d)\1{13}$/.test(d)) return false;

  const calcDigito = (slice: string, weights: number[]): number => {
    const sum = weights.reduce((acc, w, i) => acc + Number(slice[i]) * w, 0);
    const mod = sum % 11;
    return mod < 2 ? 0 : 11 - mod;
  };

  const w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

  const d1 = calcDigito(d.slice(0, 12), w1);
  const d2 = calcDigito(d.slice(0, 13), w2);

  return Number(d[12]) === d1 && Number(d[13]) === d2;
}
