"use client";

import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgenda } from "@/hooks/use-agenda";
import { cn } from "@/lib/utils";
import type { EventoAgenda } from "@/lib/schemas/agenda";

const NOMES_DIAS = ["D", "S", "T", "Q", "Q", "S", "S"];

const STATUS_COR: Record<string, string> = {
  pago: "bg-[var(--color-lime-d)] text-[var(--color-lime)] border-[rgba(163,255,107,0.32)]",
  pendente: "bg-[var(--color-amber-d)] text-[var(--color-amber)] border-[rgba(255,184,77,0.32)]",
  atrasado: "bg-[var(--color-red-d)] text-[var(--color-red)] border-[rgba(255,85,102,0.32)]",
  informativo: "bg-[var(--color-blue-d)] text-[var(--color-blue)] border-[rgba(77,142,255,0.32)]",
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
    <Card className="p-5 flex flex-col gap-3 lg:col-span-2">
      <div className="flex items-center gap-2">
        <CalendarDays className="size-4 text-[var(--color-blue)]" />
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Calendário fiscal · {nomeMes(mes)} de {ano}
        </span>
      </div>

      <div className="grid grid-cols-7 gap-1">
        {NOMES_DIAS.map((d, i) => (
          <span
            key={`hd-${i}`}
            className="text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-txt-3)] text-center mono py-1"
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
                "aspect-square rounded-md border flex flex-col items-center justify-center text-xs",
                principal
                  ? STATUS_COR[principal] ?? STATUS_COR.informativo
                  : "bg-[var(--color-card-2)] text-[var(--color-txt-3)] border-[var(--color-line-2)]",
                isHoje && "ring-2 ring-[var(--color-lime)]/60"
              )}
            >
              <span className="mono font-bold">{dia}</span>
              {eventos.length > 0 ? (
                <span className="mono text-[8px] mt-0.5">{eventos.length}</span>
              ) : null}
            </div>
          );
        })}
      </div>

      <Legenda />

      {isLoading ? <Skeleton className="h-4 w-40" /> : null}
    </Card>
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
