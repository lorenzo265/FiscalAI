"use client";

import * as React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Framed } from "@/components/blueprint/framed";
import { Ruler } from "@/components/blueprint/ruler";
import { useFiscalHistorico } from "@/hooks/use-fiscal-historico";
import { formatarMoedaCompacta } from "@/lib/format/moeda";

export function GraficoReceitaImposto() {
  const { data, isLoading } = useFiscalHistorico(6);

  const dados = (data ?? []).map((d) => ({
    rotulo: d.rotulo,
    Receita: d.receita,
    Imposto: d.imposto,
  }));

  return (
    <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden lg:col-span-2">
      {/* cabeçalho */}
      <div className="flex items-center justify-between gap-2 px-5 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-[var(--color-green)]" aria-hidden />
          <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-ink-2)]">
            Receita × imposto · últimos 6 meses
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-[var(--color-ink-2)]">
          <LegendaItem cor="var(--color-green)" texto="Receita" />
          <LegendaItem cor="var(--color-ochre)" texto="Imposto" />
        </div>
      </div>
      <Ruler />

      <div className="h-56 px-3 py-3 -ml-2">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dados} margin={{ top: 5, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--color-rule)" vertical={false} />
              <XAxis
                dataKey="rotulo"
                tick={{ fill: "var(--color-ink-3)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                stroke="var(--color-rule)"
              />
              <YAxis
                tickFormatter={(v) => formatarMoedaCompacta(Number(v))}
                tick={{ fill: "var(--color-ink-3)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                stroke="var(--color-rule)"
                width={60}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-card)",
                  border: "1px solid var(--color-rule)",
                  borderRadius: 2,
                  fontSize: 12,
                  color: "var(--color-ink)",
                  fontFamily: "var(--font-mono)",
                }}
                labelStyle={{ color: "var(--color-ink-3)" }}
                formatter={(v: number) => formatarMoedaCompacta(v)}
              />
              <Line
                type="monotone"
                dataKey="Receita"
                stroke="var(--color-green)"
                strokeWidth={2}
                dot={{ fill: "var(--color-green)", r: 3 }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="Imposto"
                stroke="var(--color-ochre)"
                strokeWidth={2}
                dot={{ fill: "var(--color-ochre)", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Framed>
  );
}

function LegendaItem({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5 mono text-[10px] font-semibold uppercase tracking-[0.12em]">
      <span className="size-2 rounded-[1px]" style={{ background: cor }} />
      {texto}
    </span>
  );
}
