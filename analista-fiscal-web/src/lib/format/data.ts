import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";

const TZ = "America/Sao_Paulo";

function toDate(value: Date | string | number): Date {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value);
  return parseISO(value);
}

export function formatarDataBR(value: Date | string | number): string {
  return format(toDate(value), "dd/MM/yyyy", { locale: ptBR });
}

export function formatarDataHoraBR(value: Date | string | number): string {
  return format(toDate(value), "dd/MM/yyyy HH:mm", { locale: ptBR });
}

export function formatarMesAnoBR(value: Date | string | number): string {
  return format(toDate(value), "MMMM 'de' yyyy", { locale: ptBR });
}

export function formatarDiaMesBR(value: Date | string | number): string {
  return format(toDate(value), "dd 'de' MMM", { locale: ptBR });
}

export function fusoBR() {
  return TZ;
}
