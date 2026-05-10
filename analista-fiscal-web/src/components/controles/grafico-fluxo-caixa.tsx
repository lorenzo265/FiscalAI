"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";
import { formatarDataBR, formatarDiaMesBR } from "@/lib/format/data";
import type { FluxoCaixaPonto } from "@/lib/schemas/controles";

interface Props {
  pontos: FluxoCaixaPonto[];
  isLoading?: boolean;
}

export function GraficoFluxoCaixa({ pontos, isLoading }: Props) {
  if (isLoading) {
    return <Skeleton className="h-72 w-full" />;
  }

  const hojeIndex = pontos.findIndex((p) => p.projecao);
  const hojeData = pontos[Math.max(0, hojeIndex - 1)]?.data;

  return (
    <div className="h-72 -ml-2">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={pontos}
          margin={{ top: 8, right: 12, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="grad-saldo-positivo" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-lime)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--color-lime)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="grad-saldo-projecao" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-blue)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--color-blue)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="data"
            tickFormatter={(v) => formatarDiaMesBR(v)}
            tick={{ fill: "var(--color-txt-3)", fontSize: 11 }}
            stroke="var(--color-line-2)"
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tickFormatter={(v) => formatarMoedaCompacta(Number(v))}
            tick={{ fill: "var(--color-txt-3)", fontSize: 11 }}
            stroke="var(--color-line-2)"
            width={70}
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
            labelFormatter={(v) => formatarDataBR(String(v))}
            formatter={(value: number) => [
              formatarMoeda(value),
              "Saldo",
            ]}
          />
          <ReferenceLine y={0} stroke="var(--color-red)" strokeDasharray="3 3" />
          {hojeData ? (
            <ReferenceLine
              x={hojeData}
              stroke="var(--color-lime)"
              strokeDasharray="3 3"
              label={{
                value: "hoje",
                fill: "var(--color-lime)",
                fontSize: 10,
                position: "top",
              }}
            />
          ) : null}
          <Area
            type="monotone"
            dataKey={(p: FluxoCaixaPonto) => (p.projecao ? null : p.saldo)}
            stroke="var(--color-lime)"
            strokeWidth={2}
            fill="url(#grad-saldo-positivo)"
            isAnimationActive={false}
            connectNulls={false}
            name="Saldo"
          />
          <Area
            type="monotone"
            dataKey={(p: FluxoCaixaPonto) => (p.projecao ? p.saldo : null)}
            stroke="var(--color-blue)"
            strokeWidth={2}
            strokeDasharray="4 4"
            fill="url(#grad-saldo-projecao)"
            isAnimationActive={false}
            connectNulls={false}
            name="Projeção"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
