"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoricoMes } from "@/lib/schemas/fiscal";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";

interface Props {
  pontos: HistoricoMes[];
  destaque: { ano: number; mes: number };
}

export function HistoricoBarChart({ pontos, destaque }: Props) {
  const data = pontos.map((m) => ({
    rotulo: m.rotulo,
    ano: m.ano,
    Imposto: m.imposto,
    Receita: m.receita,
    atual: m.ano === destaque.ano && m.mes === destaque.mes,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
          cursor={{ fill: "color-mix(in srgb, var(--color-green) 8%, transparent)" }}
          formatter={(v: number) => formatarMoeda(v)}
        />
        <Bar dataKey="Imposto" radius={[2, 2, 0, 0]}>
          {pontos.map((m) => (
            <Cell
              key={`${m.ano}-${m.mes}`}
              fill={
                m.ano === destaque.ano && m.mes === destaque.mes
                  ? "var(--color-green)"
                  : "var(--color-ink-3)"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
