"use client";

import type { Variants } from "framer-motion";
import { reveal, staggerChildren, staticVariants, defaultViewport } from "./variants";
import { useReducedMotion } from "./use-reduced-motion";

type RevealKind = "box" | "stagger";

interface UseRevealOptions {
  /** "box" = clip-wipe (Receita A); "stagger" = só orquestra filhos. */
  kind?: RevealKind;
  /** Reanima sempre que reentra no viewport (default: uma vez só). */
  repeat?: boolean;
}

interface RevealBindings {
  variants: Variants;
  initial: "hidden";
  whileInView: "show";
  viewport: { once: boolean; margin: string };
}

/**
 * Entrega as props prontas para um `motion.*` revelar ao entrar no viewport,
 * já com fallback de `prefers-reduced-motion` (mostra estático, sem movimento).
 *
 *   const r = useReveal();
 *   <motion.section {...r}>…</motion.section>
 *
 * Para escalonar filhos, use `kind: "stagger"` no pai e a variant `revealChild`
 * (ou `lineMask`) em cada filho.
 */
export function useReveal({ kind = "box", repeat = false }: UseRevealOptions = {}): RevealBindings {
  const reduced = useReducedMotion();
  const base: Variants = reduced
    ? staticVariants
    : kind === "stagger"
      ? staggerChildren
      : reveal;

  return {
    variants: base,
    initial: "hidden",
    whileInView: "show",
    viewport: { ...defaultViewport, once: !repeat },
  };
}
