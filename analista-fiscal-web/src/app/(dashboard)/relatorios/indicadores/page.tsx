"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useIndicadores } from "@/hooks/use-relatorios";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { formatarMoeda } from "@/lib/format/moeda";
import type { Indicador } from "@/lib/schemas/relatorios";
import { cn } from "@/lib/utils";

const Sparkline = dynamic(
  () =>
    import("@/components/relatorios/sparkline").then((m) => ({
      default: m.Sparkline,
    })),
  { ssr: false, loading: () => <Skeleton className="h-12 w-full" /> }
);

/* Mapear tons para tokens canônicos Arkan */
const COR_POR_TOM: Record<Indicador["tom"], string> = {
  ok: "var(--color-green)",
  warn: "var(--color-ochre)",
  error: "var(--color-danger)",
  neutral: "var(--color-ink-2)",
};

export default function IndicadoresPage() {
  const { data, isLoading, isError, refetch } = useIndicadores();
  const reduced = useReducedMotion();

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemV}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Relatórios · Indicadores
        </motion.span>
        <motion.h1
          variants={itemV}
          className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Indicadores financeiros
        </motion.h1>
        <motion.p
          variants={itemV}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Saúde financeira em 8 números. Cada painel mostra a evolução nos
          últimos 12 meses para você ver tendência, não só o valor de hoje.
        </motion.p>
      </motion.header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando indicadores..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {data.map((ind) => (
            <CardIndicador key={ind.chave} indicador={ind} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

function CardIndicador({ indicador }: { indicador: Indicador }) {
  const cor = COR_POR_TOM[indicador.tom];
  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-ink-3)] mono truncate">
            {indicador.titulo}
          </p>
          <p className="text-[11px] text-[var(--color-ink-2)] mt-1 line-clamp-2">
            {indicador.descricao}
          </p>
        </div>
        <PillTom tom={indicador.tom} />
      </div>

      <p
        className="mono text-2xl font-bold text-[var(--color-ink)] leading-tight"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {formatarValor(indicador)}
      </p>

      <Variacao indicador={indicador} />

      <Sparkline serie={indicador.serie} cor={cor} formato={indicador.formato} />
    </Framed>
  );
}

function PillTom({ tom }: { tom: Indicador["tom"] }) {
  const label = {
    ok: "saudável",
    warn: "atenção",
    error: "crítico",
    neutral: "—",
  } as const;
  return <Pill tom={tom}>{label[tom]}</Pill>;
}

function Variacao({ indicador }: { indicador: Indicador }) {
  if (indicador.direcao === "estavel") {
    return (
      <span className="flex items-center gap-1 text-[11px] text-[var(--color-ink-3)]">
        <Minus className="size-3" /> estável vs mês anterior
      </span>
    );
  }
  const Icon = indicador.direcao === "alta" ? TrendingUp : TrendingDown;
  const positivo = indicador.direcao === "alta";
  const cor = positivo ? "var(--color-green)" : "var(--color-danger)";
  return (
    <span
      className={cn("flex items-center gap-1 text-[11px] mono")}
      style={{ color: cor, fontVariantNumeric: "tabular-nums" }}
    >
      <Icon className="size-3" />
      {(indicador.variacao >= 0 ? "+" : "") +
        indicador.variacao.toFixed(1).replace(".", ",")}
      %
      <span className="text-[var(--color-ink-3)]">vs mês anterior</span>
    </span>
  );
}

function formatarValor(ind: Indicador): string {
  switch (ind.formato) {
    case "moeda":
      return formatarMoeda(ind.valor);
    case "percentual":
      return `${ind.valor.toFixed(1).replace(".", ",")}%`;
    case "dias":
      return `${Math.round(ind.valor)} dias`;
    case "decimal":
      return ind.valor.toFixed(2).replace(".", ",");
  }
}
