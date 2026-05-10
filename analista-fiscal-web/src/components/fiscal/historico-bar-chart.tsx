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
          cursor={{ fill: "rgba(163,255,107,0.06)" }}
          formatter={(v: number) => formatarMoeda(v)}
        />
        <Bar dataKey="Imposto" radius={[4, 4, 0, 0]}>
          {pontos.map((m) => (
            <Cell
              key={`${m.ano}-${m.mes}`}
              fill={
                m.ano === destaque.ano && m.mes === destaque.mes
                  ? "var(--color-lime)"
                  : "var(--color-blue)"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
