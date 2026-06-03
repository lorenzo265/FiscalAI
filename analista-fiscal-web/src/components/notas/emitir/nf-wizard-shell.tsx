"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { EASE, DUR } from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

interface Passo {
  numero: number;
  titulo: string;
}

interface Props {
  passos: Passo[];
  passoAtual: number;
  children: React.ReactNode;
}

/**
 * NfWizardShell — barra de progresso no estilo técnico Arkan:
 * índice mono + fio de conexão 1px + checkmark em verde para concluídos.
 * Sem rounded-full (pílula). Transição de passo suave via Framer AnimatePresence.
 */
export function NfWizardShell({ passos, passoAtual, children }: Props) {
  const reduced = useReducedMotion();

  return (
    <div className="flex flex-col gap-6">
      {/* ── barra de progresso técnica ── */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1" role="list" aria-label="Passos do assistente de emissão">
        {passos.map((p, i) => {
          const concluido = p.numero < passoAtual;
          const atual = p.numero === passoAtual;
          return (
            <React.Fragment key={p.numero}>
              <div
                className="flex items-center gap-2 shrink-0"
                role="listitem"
                aria-current={atual ? "step" : undefined}
              >
                {/* indicador de passo — quadrado 2px, não círculo pílula */}
                <div
                  className={cn(
                    "size-7 rounded-[var(--radius-md)] grid place-items-center text-[12px] font-bold mono transition-colors border",
                    concluido
                      ? "bg-[var(--color-green)] border-[var(--color-green)] text-[var(--color-card)]"
                      : atual
                        ? "bg-[var(--color-green-wash)] border-[var(--color-green)] text-[var(--color-green)]"
                        : "bg-[var(--color-paper-2)] border-[var(--color-rule-2)] text-[var(--color-ink-3)]"
                  )}
                >
                  {concluido ? <Check className="size-3.5" /> : (
                    <span style={{ fontVariantNumeric: "tabular-nums" }}>
                      {p.numero}
                    </span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-[12px] font-semibold uppercase tracking-[0.12em] mono transition-colors",
                    atual
                      ? "text-[var(--color-ink)]"
                      : concluido
                        ? "text-[var(--color-ink-2)]"
                        : "text-[var(--color-ink-3)]"
                  )}
                >
                  {p.titulo}
                </span>
              </div>
              {/* fio de conexão 1px */}
              {i < passos.length - 1 ? (
                <div
                  className={cn(
                    "h-px flex-1 min-w-[24px] transition-colors",
                    concluido
                      ? "bg-[var(--color-green)]"
                      : "bg-[var(--color-rule-2)]"
                  )}
                  aria-hidden
                />
              ) : null}
            </React.Fragment>
          );
        })}
      </div>

      {/* ── conteúdo do passo com transição suave ── */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={passoAtual}
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0, y: -6 }}
          transition={{ duration: DUR.base, ease: EASE.settle }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
