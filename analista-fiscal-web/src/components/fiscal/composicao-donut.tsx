"use client";

import * as React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { ComposicaoTributo } from "@/lib/schemas/fiscal";
import { formatarMoeda } from "@/lib/format/moeda";

const CORES = [
  "var(--color-lime)",
  "var(--color-blue)",
  "var(--color-amber)",
  "#9b8cff",
  "#ff8e7a",
  "#5fd2c2",
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
              stroke="var(--color-bg)"
              strokeWidth={2}
            >
              {dados.map((_, i) => (
                <Cell key={i} fill={CORES[i % CORES.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--color-card-2)",
                border: "1px solid var(--color-line-2)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--color-txt)",
              }}
              formatter={(v: number, _n, p) => [
                formatarMoeda(v),
                (p?.payload as { apelido?: string })?.apelido ?? "",
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-txt-3)] mono">
            Total mês
          </span>
          <span className="mono text-xl font-bold text-[var(--color-txt)] mt-1">
            {formatarMoeda(total)}
          </span>
        </div>
      </div>

      <ul className="flex flex-col gap-1.5">
        {dados.map((d, i) => (
          <li
            key={d.name}
            className="flex items-center gap-3 py-1.5 px-2 rounded-md hover:bg-[var(--color-card-2)] transition-colors"
          >
            <span
              className="size-2.5 rounded-sm shrink-0"
              style={{ background: CORES[i % CORES.length] }}
            />
            <span className="text-sm text-[var(--color-txt)] flex-1 truncate">
              {d.apelido}
            </span>
            <span className="mono text-xs text-[var(--color-txt-3)]">
              {(d.percentual * 100).toFixed(0)}%
            </span>
            <span className="mono text-sm font-semibold text-[var(--color-txt)] w-24 text-right">
              {formatarMoeda(d.value)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
