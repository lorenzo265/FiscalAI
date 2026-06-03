"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Logo } from "@/components/layout/logo";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { useOnboardingStore, ONBOARDING_TOTAL_PASSOS } from "@/lib/stores/onboarding-store";
import {
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";

const TITULOS: Record<number, { titulo: string; subtitulo: string; fig: string }> = {
  1: { titulo: "Vamos achar sua empresa",   subtitulo: "Comece pelo CNPJ — buscamos o resto.", fig: "Identificação" },
  2: { titulo: "Como você é tributado?",    subtitulo: "Isso define quais módulos você usa.",  fig: "Regime tributário" },
  3: { titulo: "Certificado digital A1",    subtitulo: "O que permite emitir nota fiscal.",    fig: "Certificado" },
  4: { titulo: "Conecte suas contas",       subtitulo: "Conciliação automática via Open Finance.", fig: "Open Finance" },
  5: { titulo: "Tudo pronto",               subtitulo: "Confira o resumo e entre no painel.", fig: "Resumo" },
};

export function WizardShell({ children }: { children: React.ReactNode }) {
  const passo = useOnboardingStore((s) => s.passo);
  const meta = TITULOS[passo] ?? TITULOS[1]!;
  const reduced = useReducedMotion();

  const itemVariants = reduced ? staticVariants : revealChild;
  const containerVariants = reduced ? staticVariants : staggerChildren;

  return (
    <div className="w-full max-w-[760px] flex flex-col gap-6">
      {/* identidade Arkan */}
      <motion.div
        className="flex items-center gap-3"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={itemVariants}>
          <Logo size={36} />
        </motion.div>
        <motion.div className="leading-tight" variants={itemVariants}>
          <p className="text-sm font-semibold text-[var(--color-ink)]">Arkan</p>
          <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-ink-3)] mono">
            Cadastro · passo {passo} de {ONBOARDING_TOTAL_PASSOS}
          </p>
        </motion.div>
      </motion.div>

      {/* indicadores de passo — quadrados técnicos em vez de pills */}
      <IndicadoresPassos passo={passo} total={ONBOARDING_TOTAL_PASSOS} />

      {/* painel principal com linguagem Instrumento */}
      <Framed marks tone="rule" surface="card" padded={false}>
        {/* Fig. rotulando o passo atual */}
        <div className="px-7 pt-5 pb-4 border-b" style={{ borderColor: "var(--color-rule)" }}>
          <Fig n={passo} titulo={meta.fig} size="sm" />
        </div>

        <div className="px-7 pt-5 pb-2">
          <h1 className="font-serif text-2xl tracking-tight text-[var(--color-ink)] leading-tight">
            {meta.titulo}
          </h1>
          <p className="text-sm text-[var(--color-ink-2)] mt-1">{meta.subtitulo}</p>
        </div>

        {/* conteúdo do passo com AnimatePresence */}
        <AnimatePresence mode="wait">
          <motion.div
            key={passo}
            className="px-7 pb-7"
            initial={reduced ? { opacity: 1 } : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 1 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </Framed>
    </div>
  );
}

function IndicadoresPassos({ passo, total }: { passo: number; total: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }, (_, i) => i + 1).map((n) => {
        const concluido = n < passo;
        const atual = n === passo;
        const futuro = n > passo;
        return (
          <div
            key={n}
            className={cn(
              "h-1.5 flex-1 rounded-[var(--radius-sm)] transition-colors duration-300",
              concluido && "bg-[var(--color-green)]",
              atual && "bg-[var(--color-green)]",
              futuro && "bg-[var(--color-rule)]"
            )}
            style={
              atual
                ? { boxShadow: "0 0 8px rgba(19,106,65,0.35)" }
                : undefined
            }
            aria-label={`Passo ${n}${concluido ? " concluído" : atual ? " atual" : ""}`}
          />
        );
      })}
    </div>
  );
}
