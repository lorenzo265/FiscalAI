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
import type { RegimeSimulado } from "@/lib/fiscal/simulador-regime";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";

interface PontoSimulador {
  rotulo: string;
  Imposto: number;
  regime: RegimeSimulado;
}

interface Props {
  pontos: PontoSimulador[];
  cores: Record<RegimeSimulado, string>;
}

export function SimuladorBarChart({ pontos, cores }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={pontos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
          width={64}
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
        <Bar dataKey="Imposto" radius={[6, 6, 0, 0]}>
          {pontos.map((d) => (
            <Cell key={d.regime} fill={cores[d.regime]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
