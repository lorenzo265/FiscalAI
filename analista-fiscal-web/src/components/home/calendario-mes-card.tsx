"use client";

import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useAgenda } from "@/hooks/use-agenda";
import { cn } from "@/lib/utils";
import type { EventoAgenda } from "@/lib/schemas/agenda";

const NOMES_DIAS = ["D", "S", "T", "Q", "Q", "S", "S"];

/**
 * Cores por status usando tokens canônicos.
 * Sem hardcode de rgba.
 */
const STATUS_COR: Record<string, string> = {
  pago: "bg-[var(--color-green-wash)] text-[var(--color-green-deep)] border-[var(--color-green)]/25",
  pendente: "bg-[var(--color-paper-2)] text-[var(--color-ochre)] border-[var(--color-ochre)]/25",
  atrasado: "bg-[var(--color-paper-2)] text-[var(--color-danger)] border-[var(--color-danger)]/25",
  informativo: "bg-[var(--color-paper-2)] text-[var(--color-ink-2)] border-[var(--color-rule)]",
};

export function CalendarioMesCard() {
  const { data, isLoading } = useAgenda();
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();
  const ultimoDia = new Date(ano, mes + 1, 0).getDate();
  const primeiroDiaSemana = new Date(ano, mes, 1).getDay();

  const eventosPorDia = agruparPorDia(data ?? []);

  return (
    <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden lg:col-span-2">
      {/* cabeçalho */}
      <div className="flex items-center gap-2 px-5 pt-4 pb-2">
        <CalendarDays className="size-4 text-[var(--color-ink-2)]" aria-hidden />
        <Fig n={5} titulo={`Calendário fiscal · ${nomeMes(mes)} de ${ano}`} size="sm" />
      </div>
      <Ruler />

      <div className="px-5 py-4 flex flex-col gap-3">
        <div className="grid grid-cols-7 gap-1">
          {NOMES_DIAS.map((d, i) => (
            <span
              key={`hd-${i}`}
              className="text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-ink-3)] text-center mono py-1"
            >
              {d}
            </span>
          ))}

          {Array.from({ length: primeiroDiaSemana }).map((_, i) => (
            <span key={`empty-${i}`} />
          ))}

          {Array.from({ length: ultimoDia }).map((_, i) => {
            const dia = i + 1;
            const eventos = eventosPorDia.get(dia) ?? [];
            const principal = principalDoDia(eventos);
            const isHoje = dia === hoje.getDate();
            return (
              <div
                key={`dia-${dia}`}
                className={cn(
                  "aspect-square rounded-[var(--radius-md)] border flex flex-col items-center justify-center text-xs",
                  principal
                    ? STATUS_COR[principal] ?? STATUS_COR.informativo
                    : "bg-[var(--color-paper-2)] text-[var(--color-ink-3)] border-[var(--color-rule)]",
                  isHoje && "outline outline-2 outline-offset-1 outline-[var(--color-green)]"
                )}
              >
                <span className="mono font-bold" style={{ fontVariantNumeric: "tabular-nums" }}>{dia}</span>
                {eventos.length > 0 ? (
                  <span className="mono text-[8px] mt-0.5">{eventos.length}</span>
                ) : null}
              </div>
            );
          })}
        </div>

        <Legenda />

        {isLoading ? <Skeleton className="h-4 w-40" /> : null}
      </div>
    </Framed>
  );
}

function Legenda() {
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      <Pill tom="ok">pago</Pill>
      <Pill tom="warn">a fazer</Pill>
      <Pill tom="error">atrasado</Pill>
      <Pill tom="info">informativo</Pill>
    </div>
  );
}

function agruparPorDia(eventos: EventoAgenda[]): Map<number, EventoAgenda[]> {
  const map = new Map<number, EventoAgenda[]>();
  for (const e of eventos) {
    const dia = Number(e.data.split("-")[2]);
    const arr = map.get(dia) ?? [];
    arr.push(e);
    map.set(dia, arr);
  }
  return map;
}

function principalDoDia(eventos: EventoAgenda[]): string | null {
  if (eventos.length === 0) return null;
  if (eventos.some((e) => e.status === "atrasado")) return "atrasado";
  if (eventos.some((e) => e.status === "pendente")) return "pendente";
  if (eventos.some((e) => e.status === "pago")) return "pago";
  return "informativo";
}

function nomeMes(idx: number): string {
  const meses = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
  ];
  return meses[idx] ?? "—";
}
