"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
} from "lucide-react";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Carimbo } from "@/components/blueprint/carimbo";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const TOM_PALETA: Record<
  "ok" | "warn" | "error",
  { color: string; bg: string; tomPill: PillTom; carimboTom: "green" | "ink" | "danger" }
> = {
  ok: {
    color: "var(--color-green)",
    bg: "var(--color-green-wash)",
    tomPill: "ok",
    carimboTom: "green",
  },
  warn: {
    color: "var(--color-ochre)",
    bg: "var(--color-paper-2)",
    tomPill: "warn",
    carimboTom: "ink",
  },
  error: {
    color: "var(--color-danger)",
    bg: "var(--color-paper-2)",
    tomPill: "error",
    carimboTom: "danger",
  },
};

export function FiscalHealthScore() {
  const { data, isLoading, isError, refetch } = useFiscalSaude();
  const reduced = useReducedMotion();

  if (isLoading)
    return <LoadingState titulo="Calculando seu Índice de Saúde Fiscal..." />;
  if (isError || !data) {
    return <ErrorState onTentarNovamente={() => void refetch()} />;
  }

  const paleta = TOM_PALETA[data.tom];
  const Icon =
    data.tom === "ok"
      ? CheckCircle2
      : data.tom === "warn"
        ? AlertTriangle
        : AlertOctagon;

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  return (
    <motion.section
      variants={pageReveal}
      initial="hidden"
      animate="show"
      aria-label="Índice de Saúde Fiscal"
    >
      <Framed marks tone="ink" surface="card" className="flex flex-col gap-5 md:gap-0 md:flex-row md:items-start">
        {/* ── núcleo do score ── */}
        <motion.div
          className="flex items-center gap-5 md:gap-6"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {/* medidor — quadrado técnico, não rounded-2xl */}
          <motion.div variants={itemVariants}>
            <div
              className="size-24 rounded-[var(--radius-md)] grid place-items-center relative border"
              style={{
                background: paleta.bg,
                borderColor: paleta.color,
              }}
            >
              <span
                className="mono font-extrabold leading-none"
                style={{ color: paleta.color, fontSize: "44px", fontVariantNumeric: "tabular-nums" }}
              >
                {data.score}
              </span>
              {/* Fig. 01 no canto superior */}
              <span
                className="absolute top-1 left-1.5 mono text-[8px] uppercase tracking-[0.12em] font-semibold"
                style={{ color: paleta.color, opacity: 0.7 }}
              >
                FIG.01
              </span>
            </div>
          </motion.div>

          <motion.div className="flex flex-col gap-2" variants={containerVariants}>
            <motion.div variants={itemVariants}>
              <Pill tom={paleta.tomPill}>
                <Icon className="size-3 inline mr-1" aria-hidden />
                Índice de Saúde Fiscal
              </Pill>
            </motion.div>
            <motion.h2
              variants={itemVariants}
              className="font-serif text-2xl md:text-[28px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              {data.titulo}
            </motion.h2>
            <motion.p
              variants={itemVariants}
              className="text-sm text-[var(--color-ink-2)] max-w-md leading-relaxed"
            >
              {data.descricao}
            </motion.p>
            <motion.div variants={itemVariants} className="mt-1 max-w-sm">
              <Progress
                value={data.score}
                tom={
                  data.tom === "ok"
                    ? "lime"
                    : data.tom === "warn"
                      ? "amber"
                      : "red"
                }
              />
            </motion.div>
          </motion.div>
        </motion.div>

        <div className="flex-1" />

        {/* ── grade de componentes ── */}
        <div className="grid grid-cols-3 gap-2 w-full md:w-auto md:max-w-[400px]">
          {data.componentes.slice(0, 6).map((c) => (
            <ComponenteMini
              key={c.categoria}
              label={c.label}
              pontuacao={c.pontuacao}
              tom={c.tom}
            />
          ))}
        </div>

        {/* ── signature: Carimbo de saúde fiscal (estado ok) ── */}
        {data.tom === "ok" ? (
          <div className="flex flex-col items-end justify-end gap-3 ml-4 shrink-0">
            <Carimbo tom="green" sub="saúde fiscal">
              Conforme
            </Carimbo>
          </div>
        ) : data.alertasPrioritarios[0]?.acao ? (
          <Button asChild variant="outline" size="sm" className="hidden md:flex self-end">
            <Link href={data.alertasPrioritarios[0].acao.rota}>
              {data.alertasPrioritarios[0].acao.label}
              <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        ) : null}
      </Framed>
    </motion.section>
  );
}

function ComponenteMini({
  label,
  pontuacao,
  tom,
}: {
  label: string;
  pontuacao: number;
  tom: "ok" | "warn" | "error";
}) {
  const cor = TOM_PALETA[tom].color;
  return (
    <div
      className="rounded-[var(--radius-md)] p-2 border flex flex-col gap-0.5"
      style={{
        background: "var(--color-paper-2)",
        borderColor: "var(--color-rule-2)",
      }}
    >
      <span className="text-[9px] uppercase tracking-[0.12em] font-bold text-[var(--color-ink-3)] truncate">
        {label}
      </span>
      <span
        className="mono text-sm font-bold"
        style={{ color: cor, fontVariantNumeric: "tabular-nums" }}
      >
        {pontuacao}
        <span className="text-[var(--color-ink-3)] text-[10px] ml-0.5">/100</span>
      </span>
    </div>
  );
}
