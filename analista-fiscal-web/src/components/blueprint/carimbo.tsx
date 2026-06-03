"use client";

import * as React from "react";
import { motion, type MotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { stamp, stampRing } from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/**
 * Carimbo — o selo que "bate" no parecer/estado resolvido (assinatura própria do
 * Arkan, Receita F). Único lugar do sistema com overshoot (`--ease-stamp`).
 * Borda dupla + texto mono caixa-alta, levemente girado, com anel de "tinta" que
 * expande e some atrás.
 *
 * Tons: `green` (aprovado/conforme — o acento), `ink` (registrado/arquivado),
 * `danger` (rejeitado/pendência grave — dentro do mundo quente).
 * Fallback `prefers-reduced-motion`: aparece pronto, sem overshoot nem anel.
 */
type CarimboTom = "green" | "ink" | "danger";

interface CarimboProps {
  children: React.ReactNode;
  tom?: CarimboTom;
  /** Sub-rótulo opcional em mono menor (ex.: data, protocolo). */
  sub?: React.ReactNode;
  /** Dispara o carimbo ao entrar no viewport em vez de no mount. */
  inView?: boolean;
  className?: string;
}

const tomMap: Record<CarimboTom, { color: string; ring: string }> = {
  green: { color: "var(--color-green)", ring: "var(--color-green)" },
  ink: { color: "var(--color-ink)", ring: "var(--color-ink)" },
  danger: { color: "var(--color-danger)", ring: "var(--color-danger)" },
};

export function Carimbo({ children, tom = "green", sub, inView = false, className }: CarimboProps) {
  const reduced = useReducedMotion();
  const { color, ring } = tomMap[tom];

  const trigger: MotionProps = reduced
    ? { animate: "show", initial: false }
    : inView
      ? {
          initial: "hidden",
          whileInView: "show",
          viewport: { once: true, margin: "0px 0px -10% 0px" },
        }
      : { initial: "hidden", animate: "show" };

  return (
    <span className={cn("relative inline-flex select-none", className)}>
      {/* anel de tinta atrás */}
      {!reduced ? (
        <motion.span
          aria-hidden="true"
          variants={stampRing}
          {...trigger}
          className="pointer-events-none absolute inset-0 rounded-[3px]"
          style={{ border: `2px solid ${ring}` }}
        />
      ) : null}

      <motion.span
        variants={stamp}
        {...trigger}
        className={cn(
          "mono inline-flex flex-col items-center gap-0.5 rounded-[3px] px-3 py-1.5",
          "uppercase tracking-[0.18em] font-bold text-[11px]",
          "[border:2px_solid] [box-shadow:inset_0_0_0_1px_var(--color-paper)]"
        )}
        style={{ color, borderColor: color }}
      >
        <span className="leading-none">{children}</span>
        {sub ? (
          <span className="text-[8px] font-semibold tracking-[0.14em] opacity-80 leading-none">
            {sub}
          </span>
        ) : null}
      </motion.span>
    </span>
  );
}
