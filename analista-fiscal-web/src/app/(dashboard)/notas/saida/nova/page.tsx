"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { NfWizardShell } from "@/components/notas/emitir/nf-wizard-shell";
import { PassoDestinatario } from "@/components/notas/emitir/passo-destinatario";
import { PassoItens } from "@/components/notas/emitir/passo-itens";
import { PassoPagamento } from "@/components/notas/emitir/passo-pagamento";
import { PassoEmissao } from "@/components/notas/emitir/passo-emissao";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const PASSOS = [
  { numero: 1, titulo: "Destinatário" },
  { numero: 2, titulo: "Itens" },
  { numero: 3, titulo: "Pagamento" },
  { numero: 4, titulo: "Emissão" },
];

export default function EmitirNotaPage() {
  const passo = useNfWizardStore((s) => s.passo);
  const reduced = useReducedMotion();

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  React.useEffect(() => {
    return () => {
      // Mantém o draft entre navegações para o usuário não perder.
      // Reset explícito ocorre via "Emitir outra nota".
    };
  }, []);

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
          Módulo · Notas
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Emitir nota fiscal
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Em 4 passos. Sistema calcula CFOP, NCM, CST e alíquotas automaticamente.
        </motion.p>
      </motion.header>

      <NfWizardShell passos={PASSOS} passoAtual={passo}>
        {passo === 1 ? <PassoDestinatario /> : null}
        {passo === 2 ? <PassoItens /> : null}
        {passo === 3 ? <PassoPagamento /> : null}
        {passo === 4 ? <PassoEmissao /> : null}
      </NfWizardShell>
    </motion.div>
  );
}
