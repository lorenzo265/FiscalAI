"use client";

import * as React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { ComposicaoTributo } from "@/lib/schemas/fiscal";
import { formatarMoeda } from "@/lib/format/moeda";

/**
 * Paleta canônica: verde (acento), ink-2 (neutro primário), ink-3 (neutro
 * secundário), ochre (atenção), graphite (suporte). Nunca azul/roxo neon.
 * Donut com fio stroke papel — sem borda branca genérica.
 */
const CORES = [
  "var(--color-green)",
  "var(--color-ink-2)",
  "var(--color-ochre)",
  "var(--color-ink-3)",
  "var(--color-green-bright)",
  "var(--color-graphite)",
];

type Props = {
  composicao: ComposicaoTributo[];
  total: number;
};

export function ComposicaoDonut({ composicao, total }: Props) {
  const dados = composicao.map((c) => ({
    name: c.tributo,
    apelido: c.apelido,
    value: Math.round(c.valor),
    percentual: c.percentual,
  }));

  return (
    <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-5 items-center">
      <div className="relative h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={dados}
              dataKey="value"
              innerRadius={70}
              outerRadius={95}
              paddingAngle={2}
              stroke="var(--color-card)"
              strokeWidth={2}
            >
              {dados.map((_, i) => (
                <Cell key={i} fill={CORES[i % CORES.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--color-card)",
                border: "1px solid var(--color-rule)",
                borderRadius: 2,
                fontSize: 12,
                color: "var(--color-ink)",
                fontFamily: "var(--font-mono)",
              }}
              formatter={(v: number, _n, p) => [
                formatarMoeda(v),
                (p?.payload as { apelido?: string })?.apelido ?? "",
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-ink-3)] mono">
            Total mês
          </span>
          <span
            className="mono text-xl font-bold text-[var(--color-ink)] mt-1"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarMoeda(total)}
          </span>
        </div>
      </div>

      <ul className="flex flex-col gap-1.5">
        {dados.map((d, i) => (
          <li
            key={d.name}
            className="flex items-center gap-3 py-1.5 px-2 rounded-[var(--radius-md)] hover:bg-[var(--color-paper-2)] transition-colors"
          >
            <span
              className="size-2.5 rounded-[1px] shrink-0"
              style={{ background: CORES[i % CORES.length] }}
            />
            <span className="text-sm text-[var(--color-ink)] flex-1 truncate">
              {d.apelido}
            </span>
            <span
              className="mono text-xs text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {(d.percentual * 100).toFixed(0)}%
            </span>
            <span
              className="mono text-sm font-semibold text-[var(--color-ink)] w-24 text-right"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatarMoeda(d.value)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
