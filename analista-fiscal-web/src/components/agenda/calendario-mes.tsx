"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { COR_STATUS_AGENDA } from "@/components/agenda/status-evento-pill";
import type { EventoAgenda } from "@/lib/schemas/agenda";

interface Props {
  ano: number;
  mes: number; // 1-12
  eventos: EventoAgenda[];
  hoje?: Date;
  onSelecionar?: (evento: EventoAgenda) => void;
}

const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

export function CalendarioMes({
  ano,
  mes,
  eventos,
  hoje = new Date(),
  onSelecionar,
}: Props) {
  const primeiroDia = new Date(ano, mes - 1, 1);
  const ultimoDia = new Date(ano, mes, 0);
  const diasNoMes = ultimoDia.getDate();
  const offsetInicio = primeiroDia.getDay();
  const totalCelulas = Math.ceil((offsetInicio + diasNoMes) / 7) * 7;

  const eventosPorDia = React.useMemo(() => {
    const map = new Map<number, EventoAgenda[]>();
    for (const e of eventos) {
      const d = new Date(e.data);
      if (d.getFullYear() !== ano || d.getMonth() !== mes - 1) continue;
      const dia = d.getDate();
      const arr = map.get(dia) ?? [];
      arr.push(e);
      map.set(dia, arr);
    }
    return map;
  }, [eventos, ano, mes]);

  const isMesAtual =
    hoje.getFullYear() === ano && hoje.getMonth() === mes - 1;
  const diaHoje = hoje.getDate();

  const celulas: React.ReactNode[] = [];
  for (let i = 0; i < totalCelulas; i++) {
    const numeroDia = i - offsetInicio + 1;
    const dentro = numeroDia >= 1 && numeroDia <= diasNoMes;
    const eventosDoDia = dentro ? eventosPorDia.get(numeroDia) ?? [] : [];
    const ehHoje = dentro && isMesAtual && numeroDia === diaHoje;

    celulas.push(
      <div
        key={i}
        className={cn(
          "min-h-[88px] flex flex-col gap-1 p-2 border-r border-b text-xs",
          !dentro && "opacity-30",
          ehHoje && "bg-[var(--color-green-wash)]"
        )}
        style={{ borderColor: "var(--color-rule)" }}
      >
        {dentro ? (
          <>
            <span
              className={cn(
                "mono text-[11px] font-bold",
                ehHoje
                  ? "text-[var(--color-green)]"
                  : "text-[var(--color-ink-2)]"
              )}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {numeroDia}
            </span>
            <ul className="flex flex-col gap-1">
              {eventosDoDia.slice(0, 3).map((e) => (
                <li key={e.id}>
                  <button
                    type="button"
                    onClick={() => onSelecionar?.(e)}
                    className="w-full text-left px-1.5 py-0.5 rounded-[var(--radius-sm)] text-[10px] truncate transition-colors hover:opacity-80 mono"
                    style={{
                      background: corBgEvento(e.status),
                      color: COR_STATUS_AGENDA[e.status],
                      borderLeft: `2px solid ${COR_STATUS_AGENDA[e.status]}`,
                    }}
                    title={e.titulo}
                  >
                    {e.titulo}
                  </button>
                </li>
              ))}
              {eventosDoDia.length > 3 ? (
                <li>
                  <span className="text-[10px] mono text-[var(--color-ink-3)]">
                    +{eventosDoDia.length - 3} eventos
                  </span>
                </li>
              ) : null}
            </ul>
          </>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* cabecalho dos dias da semana */}
      <div
        className="grid grid-cols-7 border-t border-l"
        style={{ borderColor: "var(--color-rule)" }}
      >
        {DIAS_SEMANA.map((d) => (
          <div
            key={d}
            className="px-2 py-2 border-r border-b bg-[var(--color-paper-2)] text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]"
            style={{ borderColor: "var(--color-rule)" }}
          >
            {d}
          </div>
        ))}
      </div>
      {/* grid de células */}
      <div
        className="grid grid-cols-7 border-l"
        style={{ borderColor: "var(--color-rule)" }}
      >
        {celulas}
      </div>
    </div>
  );
}

function corBgEvento(status: EventoAgenda["status"]): string {
  switch (status) {
    case "pago":        return "var(--color-green-wash)";
    case "pendente":    return "var(--color-paper-2)";
    case "atrasado":    return "var(--color-paper-2)";
    case "informativo": return "var(--color-paper-2)";
  }
}
