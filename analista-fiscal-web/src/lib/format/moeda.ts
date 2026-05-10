const fmtBRL = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const fmtBRLSemSimbolo = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatarMoeda(valor: number): string {
  if (!Number.isFinite(valor)) return "R$ 0,00";
  return fmtBRL.format(valor);
}

export function formatarMoedaSemSimbolo(valor: number): string {
  if (!Number.isFinite(valor)) return "0,00";
  return fmtBRLSemSimbolo.format(valor);
}

export function formatarMoedaCompacta(valor: number): string {
  if (!Number.isFinite(valor)) return "R$ 0";
  const abs = Math.abs(valor);
  const sign = valor < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}R$ ${(abs / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (abs >= 1_000) return `${sign}R$ ${(abs / 1_000).toFixed(1).replace(".", ",")}k`;
  return formatarMoeda(valor);
}
