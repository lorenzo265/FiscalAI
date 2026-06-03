/**
 * Arkan — biblioteca de variants de motion (Framer Motion).
 *
 * Contrato em `docs/restructure-frontend/arkan-motion-extraction.md` (§2 tokens,
 * §3 receitas A–F). Regras invioláveis:
 *  - só animar `transform / opacity / clip-path / filter` (nunca width/height/top/left);
 *  - todo reveal tem fallback `prefers-reduced-motion` (ver `staticVariants`);
 *  - easings e durações vêm dos tokens — espelhados aqui em JS porque o Framer
 *    precisa dos números/curvas no objeto de transição.
 *
 * Uso típico:
 *   <motion.div variants={reveal} initial="hidden" whileInView="show"
 *               viewport={{ once: true, margin: "0px 0px -15% 0px" }} />
 * ou o hook `useReveal()` que já entrega initial/animate + fallback reduzido.
 */
import type { Variants, Transition } from "framer-motion";

type Bezier = [number, number, number, number];

/* ─── Tokens de motion espelhados (§2) ──────────────────────────────────── */
export const EASE: Record<"settle" | "reveal" | "stamp", Bezier> = {
  settle: [0.16, 1, 0.3, 1], // expo-out: entradas/estados
  reveal: [0.62, 0.05, 0.01, 0.99], // reveals fortes (wipe/mask)
  stamp: [0.34, 1.56, 0.4, 1], // SÓ o carimbo: leve overshoot
};

export const DUR = {
  micro: 0.16,
  base: 0.32,
  reveal: 0.78,
  line: 0.64,
};

export const STAGGER = 0.07;

/* ─── Receita A — Box revela por wipe + conteúdo escalonado ──────────────── */
/** Container: corta de cima→baixo (clip-path) e sobe levemente. */
export const reveal: Variants = {
  hidden: {
    opacity: 0,
    y: 16,
    clipPath: "inset(0 0 100% 0)",
  },
  show: {
    opacity: 1,
    y: 0,
    clipPath: "inset(0 0 0% 0)",
    transition: { duration: DUR.reveal, ease: EASE.reveal },
  },
};

/** Item filho do reveal — sobe e some o desfoque do escalonamento. */
export const revealChild: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.base, ease: EASE.settle },
  },
};

/* ─── Stagger de irmãos (§3 — stagger sequencial) ────────────────────────── */
export const staggerChildren: Variants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: STAGGER,
      delayChildren: 0.04,
    },
  },
};

/* ─── Receita C — Headline line-mask ─────────────────────────────────────
 * Use em cada linha embrulhada por um elemento overflow:hidden:
 *   <span style={{ overflow: "hidden", display: "block" }}>
 *     <motion.span variants={lineMask} style={{ display: "block" }}>…</motion.span>
 *   </span>
 * Combine com `staggerChildren` no container para escalonar linha a linha. */
export const lineMask: Variants = {
  hidden: { y: "110%" },
  show: {
    y: "0%",
    transition: { duration: DUR.reveal, ease: EASE.reveal },
  },
};

/* ─── Receita B — Mídia un-blur + scale-into-focus ───────────────────────── */
export const mediaFocus: Variants = {
  hidden: { opacity: 0, scale: 1.08, filter: "blur(10px)" },
  show: {
    opacity: 1,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: DUR.reveal, ease: EASE.reveal },
  },
};

/* ─── Receita D — Draw-on de fio/margem ──────────────────────────────────
 * Para SVG <path/line>: animar `pathLength` 0→1.
 * Para fios em DOM: animar `scaleY`/`scaleX` 0→1 com transformOrigin na ponta. */
export const drawOn: Variants = {
  hidden: { pathLength: 0, opacity: 0.4 },
  show: {
    pathLength: 1,
    opacity: 1,
    transition: { duration: DUR.line, ease: EASE.settle },
  },
};

/** Fio em DOM (não-SVG): cresce de uma ponta. transformOrigin no caller. */
export const drawLine: Variants = {
  hidden: { scaleY: 0 },
  show: {
    scaleY: 1,
    transition: { duration: DUR.line, ease: EASE.settle },
  },
};

/* ─── Receita F — Carimbo (único lugar com overshoot) ────────────────────── */
export const stamp: Variants = {
  hidden: { opacity: 0, scale: 1.7, rotate: -22 },
  show: {
    opacity: 0.92,
    scale: 1,
    rotate: -7,
    transition: { duration: 0.5, ease: EASE.stamp },
  },
};

/** Anel de "tinta" que expande e some atrás do carimbo. */
export const stampRing: Variants = {
  hidden: { opacity: 0.5, scale: 0.4 },
  show: {
    opacity: 0,
    scale: 1.8,
    transition: { duration: 0.6, ease: EASE.settle },
  },
};

/* ─── Fallback universal para reduced-motion ─────────────────────────────
 * Aplique como variants quando `useReducedMotion()` for true: tudo já visível,
 * sem transform/clip/filter. Mantém o `whileInView` funcional sem movimento. */
export const staticVariants: Variants = {
  hidden: { opacity: 1 },
  show: { opacity: 1, transition: { duration: 0 } },
};

/* ─── Transição utilitária (hover/foco/micro) ────────────────────────────── */
export const microTransition: Transition = {
  duration: DUR.micro,
  ease: EASE.settle,
};

/** Viewport padrão dos reveals: uma vez, dispara um pouco antes do fim. */
export const defaultViewport = {
  once: true,
  margin: "0px 0px -15% 0px",
} as const;
