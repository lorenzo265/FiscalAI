"use client";

import * as React from "react";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { FiscalHealthScore } from "@/components/fiscal/fiscal-health-score";
import { ProximoPagamentoCard } from "@/components/home/proximo-pagamento-card";
import { ProximaObrigacaoCard } from "@/components/home/proxima-obrigacao-card";
import { AlertasCard } from "@/components/home/alertas-card";
import { CalendarioMesCard } from "@/components/home/calendario-mes-card";
import { QuickActions } from "@/components/home/quick-actions";
import { SimplesNacionalCard } from "@/components/home/simples-nacional-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const GraficoReceitaImposto = dynamic(
  () =>
    import("@/components/home/grafico-receita-imposto").then((m) => ({
      default: m.GraficoReceitaImposto,
    })),
  { ssr: false, loading: () => <Skeleton className="h-[280px] w-full" /> }
);

export default function HomePage() {
  const { empresa } = useEmpresaAtual();
  const primeiroNome = empresa?.razaoSocial.split(" ")[0] ?? "";
  const horaSaudacao = saudacao(new Date());
  const reduced = useReducedMotion();

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
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          {horaSaudacao} · Início
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[28px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Olá{primeiroNome ? `, ${primeiroNome}` : ""}.
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] mt-1"
        >
          Resumo fiscal do dia — tudo que importa, em um só lugar.
        </motion.p>
      </motion.header>

      {/* ── Fiscal Health Score (signature da home) ── */}
      <FiscalHealthScore />

      {/* ── cards de resumo ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ProximoPagamentoCard />
        <ProximaObrigacaoCard />
        <AlertasCard />
      </div>

      {/* ── atalhos rápidos ── */}
      <QuickActions />

      {/* ── gráfico + calendário ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GraficoReceitaImposto />
        <CalendarioMesCard />
      </div>

      {/* ── simples nacional ── */}
      <div className="grid grid-cols-1 gap-4">
        <SimplesNacionalCard />
      </div>
    </motion.div>
  );
}

function saudacao(d: Date): string {
  const h = d.getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}
