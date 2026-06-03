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
          width={64}
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
          {pontos.map((d) => (
            <Cell key={d.regime} fill={cores[d.regime]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
