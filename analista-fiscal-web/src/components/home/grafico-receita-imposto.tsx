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
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
    <Card className="p-5 flex flex-col gap-3 lg:col-span-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-[var(--color-lime)]" />
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Receita × imposto · últimos 6 meses
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-[var(--color-txt-2)]">
          <Legenda cor="var(--color-lime)" texto="Receita" />
          <Legenda cor="var(--color-amber)" texto="Imposto" />
        </div>
      </div>

      <div className="h-56 -ml-2">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dados} margin={{ top: 5, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="rotulo"
                tick={{ fill: "var(--color-txt-3)", fontSize: 11 }}
                stroke="var(--color-line-2)"
              />
              <YAxis
                tickFormatter={(v) => formatarMoedaCompacta(Number(v))}
                tick={{ fill: "var(--color-txt-3)", fontSize: 11 }}
                stroke="var(--color-line-2)"
                width={60}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-card-2)",
                  border: "1px solid var(--color-line-2)",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "var(--color-txt)",
                }}
                labelStyle={{ color: "var(--color-txt-3)" }}
                formatter={(v: number) => formatarMoedaCompacta(v)}
              />
              <Line
                type="monotone"
                dataKey="Receita"
                stroke="var(--color-lime)"
                strokeWidth={2}
                dot={{ fill: "var(--color-lime)", r: 3 }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="Imposto"
                stroke="var(--color-amber)"
                strokeWidth={2}
                dot={{ fill: "var(--color-amber)", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2 rounded-full" style={{ background: cor }} />
      {texto}
    </span>
  );
}
