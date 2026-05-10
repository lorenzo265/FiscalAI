"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SparkPoint } from "@/lib/schemas/relatorios";

interface Props {
  serie: SparkPoint[];
  cor: string;
  formato: "moeda" | "percentual" | "decimal" | "dias";
}

function formatar(formato: Props["formato"], valor: number): string {
  switch (formato) {
    case "moeda":
      return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 0,
      }).format(valor);
    case "percentual":
      return `${valor.toFixed(1).replace(".", ",")}%`;
    case "dias":
      return `${Math.round(valor)} dias`;
    case "decimal":
      return valor.toFixed(2).replace(".", ",");
  }
}

export function Sparkline({ serie, cor, formato }: Props) {
  return (
    <div className="h-12 -mx-2">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={serie} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient
              id={`grad-${cor.replace(/[^a-zA-Z0-9]/g, "")}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor={cor} stopOpacity={0.4} />
              <stop offset="100%" stopColor={cor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Tooltip
            contentStyle={{
              background: "var(--color-card-2)",
              border: "1px solid var(--color-line-2)",
              borderRadius: 6,
              fontSize: 11,
              padding: "4px 8px",
              color: "var(--color-txt)",
            }}
            labelStyle={{ color: "var(--color-txt-3)", fontSize: 10 }}
            formatter={(value: number) => [formatar(formato, value), ""]}
            cursor={{ stroke: "var(--color-line-2)", strokeDasharray: 2 }}
          />
          <Area
            type="monotone"
            dataKey="valor"
            stroke={cor}
            strokeWidth={1.5}
            fill={`url(#grad-${cor.replace(/[^a-zA-Z0-9]/g, "")})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
