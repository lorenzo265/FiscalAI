"use client";

import * as React from "react";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { Calculator, TrendingDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  simular,
  type AtividadeSimulada,
  type CenarioSimulado,
  type RegimeSimulado,
} from "@/lib/fiscal/simulador-regime";
import { cn } from "@/lib/utils";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { ANEXOS } from "@/lib/traducao/obrigacoes";

const SimuladorBarChart = dynamic(
  () =>
    import("@/components/fiscal/simulador-bar-chart").then((m) => ({
      default: m.SimuladorBarChart,
    })),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> }
);

const ATIVIDADES: Array<{ id: AtividadeSimulada; label: string }> = [
  { id: "comercio", label: `${ANEXOS.I.titulo} · ${ANEXOS.I.termoTecnico}` },
  { id: "industria", label: `${ANEXOS.II.titulo} · ${ANEXOS.II.termoTecnico}` },
  { id: "servicos_anexo3", label: `${ANEXOS.III.titulo} · ${ANEXOS.III.termoTecnico}` },
  { id: "servicos_anexo5", label: `${ANEXOS.V.titulo} · ${ANEXOS.V.termoTecnico}` },
];

/**
 * Cores canônicas para o simulador.
 * Simples = verde (acento); Presumido = ink-2 (neutro); Real = ochre (atenção).
 */
const CORES_REGIME: Record<RegimeSimulado, string> = {
  SIMPLES: "var(--color-green)",
  PRESUMIDO: "var(--color-ink-2)",
  REAL: "var(--color-ochre)",
};

export default function FiscalSimuladorPage() {
  const { empresa } = useEmpresaAtual();
  const reduced = useReducedMotion();

  const [faturamento, setFaturamento] = React.useState<number>(
    empresa?.faturamento12m ?? 850_000
  );
  const [atividade, setAtividade] = React.useState<AtividadeSimulada>(
    empresa?.anexoSimples === "I"
      ? "comercio"
      : empresa?.anexoSimples === "II"
        ? "industria"
        : empresa?.anexoSimples === "V"
          ? "servicos_anexo5"
          : "servicos_anexo3"
  );
  const [funcionarios, setFuncionarios] = React.useState<number>(3);

  const resultado = React.useMemo(
    () =>
      simular({
        faturamentoAnual: Math.max(0, faturamento),
        atividade,
        numeroFuncionarios: Math.max(0, funcionarios),
      }),
    [faturamento, atividade, funcionarios]
  );

  const dadosChart = resultado.cenarios.map((c) => ({
    rotulo: c.rotulo.split("·")[0]!.trim(),
    Imposto: c.impostoTotal,
    regime: c.regime,
  }));

  const economia =
    Math.max(...resultado.cenarios.map((c) => c.impostoTotal)) -
    Math.min(...resultado.cenarios.map((c) => c.impostoTotal));

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-1"
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Fiscal
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Simulador de regime
        </motion.h1>
      </motion.header>

      <FiscalSubnav />

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* ── painel de parâmetros ── */}
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden self-start">
          <div className="flex items-center gap-2 px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
            <Calculator className="size-4 text-[var(--color-green)]" aria-hidden />
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Parâmetros
            </h2>
          </div>

          <div className="px-5 py-4 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fat">Faturamento anual</Label>
              <Input
                id="fat"
                type="number"
                min={0}
                step={10000}
                value={faturamento}
                onChange={(e) => setFaturamento(Number(e.target.value))}
                className="mono"
              />
              <span
                className="text-[11px] text-[var(--color-ink-2)] mono"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarMoeda(faturamento)}
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Atividade</Label>
              <Select
                value={atividade}
                onValueChange={(v) => setAtividade(v as AtividadeSimulada)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ATIVIDADES.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="func">Número de funcionários</Label>
              <Input
                id="func"
                type="number"
                min={0}
                value={funcionarios}
                onChange={(e) => setFuncionarios(Number(e.target.value))}
                className="mono"
              />
              <span className="text-[11px] text-[var(--color-ink-3)]">
                CLT, com salário médio de R$ 4,5k.
              </span>
            </div>

            {/* economia possível */}
            <div
              className="rounded-[var(--radius-md)] border p-3 flex flex-col gap-1"
              style={{
                background: "var(--color-green-wash)",
                borderColor: "var(--color-green)",
              }}
            >
              <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
                Economia possível
              </span>
              <span
                className="mono text-2xl font-extrabold text-[var(--color-green)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarMoedaCompacta(economia)}/ano
              </span>
              <span className="text-[11px] text-[var(--color-ink-3)] leading-snug">
                Diferença entre o regime mais caro e o mais barato.
              </span>
            </div>
          </div>
        </Framed>

        {/* ── resultados ── */}
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {resultado.cenarios.map((c) => (
              <CenarioCard
                key={c.regime}
                cenario={c}
                vencedor={resultado.vencedor === c.regime}
              />
            ))}
          </div>

          <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
            <div className="flex items-center gap-2 px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
              <TrendingDown className="size-4 text-[var(--color-ink-2)]" aria-hidden />
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Imposto anual estimado por regime
              </h2>
            </div>
            <div className="h-64 px-3 py-3 -ml-2">
              <SimuladorBarChart pontos={dadosChart} cores={CORES_REGIME} />
            </div>
          </Framed>
        </div>
      </div>
    </motion.div>
  );
}

function CenarioCard({
  cenario,
  vencedor,
}: {
  cenario: CenarioSimulado;
  vencedor: boolean;
}) {
  const tom =
    cenario.recomendacao === "vantajoso"
      ? "ok"
      : cenario.recomendacao === "neutro"
        ? "warn"
        : "error";
  const cor = CORES_REGIME[cenario.regime];
  return (
    <Framed
      marks={false}
      tone={vencedor ? "ink" : "rule"}
      surface={vencedor ? "card" : "paper"}
      className={cn("flex flex-col gap-3 relative overflow-hidden", vencedor && "ring-1 ring-[var(--color-green)]")}
      style={{
        background: vencedor ? "var(--color-green-wash)" : undefined,
      }}
    >
      {/* fio de cor de regime no topo */}
      <div
        className="absolute inset-x-0 top-0 h-[2px]"
        style={{ background: cor }}
        aria-hidden
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
          {cenario.rotulo}
        </span>
        {vencedor ? (
          <Pill tom="ok">Mais econômico</Pill>
        ) : (
          <Pill tom={tom}>{cenario.recomendacao}</Pill>
        )}
      </div>

      <div className="flex flex-col gap-0.5">
        <span
          className="mono text-3xl font-extrabold text-[var(--color-ink)] leading-none"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarMoedaCompacta(cenario.impostoTotal)}
        </span>
        <span className="text-xs text-[var(--color-ink-2)]">
          {(cenario.percentualSobreFaturamento * 100).toFixed(1).replace(".", ",")}% sobre o faturamento · ano
        </span>
      </div>

      <ul
        className="flex flex-col gap-1 border-t pt-3"
        style={{ borderColor: "var(--color-rule)" }}
      >
        {cenario.detalhamento.map((d) => (
          <li
            key={d.tributo}
            className="flex items-center justify-between text-xs"
          >
            <span className="text-[var(--color-ink-2)]">{d.tributo}</span>
            <span
              className="mono text-[var(--color-ink)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatarMoedaCompacta(d.valor)}
            </span>
          </li>
        ))}
      </ul>

      <p
        className="text-[11px] text-[var(--color-ink-3)] leading-snug border-t pt-3"
        style={{ borderColor: "var(--color-rule)" }}
      >
        {cenario.observacao}
      </p>
    </Framed>
  );
}
