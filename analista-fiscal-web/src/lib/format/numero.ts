const fmtPercent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const fmtNumero = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatarPercentual(valor: number): string {
  if (!Number.isFinite(valor)) return "0,00%";
  return fmtPercent.format(valor);
}

export function formatarNumero(valor: number, casas = 0): string {
  if (!Number.isFinite(valor)) return "0";
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(valor);
}

export function formatarInteiro(valor: number): string {
  return fmtNumero.format(Math.round(valor));
}
