"use client";

import * as React from "react";
import { motion, type MotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE, DUR, STAGGER } from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/**
 * BlueprintSchematic — desenho de engenharia em linha-grafite que **se desenha**
 * ao entrar no viewport (Receita D: draw-on por pathLength). É a assinatura
 * técnica do Arkan. Esta primeira figura é o esquemático de uma NOTA FISCAL
 * (cabeçalho, linhas de item, totais, selo) — vira uma família por feature.
 *
 * Fallback `prefers-reduced-motion`: aparece pronto (pathLength 1), sem desenho.
 * Só anima `pathLength`/`opacity` (SVG) — perf-safe.
 */
interface BlueprintSchematicProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Largura do desenho (px). Altura segue o viewBox. */
  width?: number;
  /** Variante de figura. Hoje: a nota; extensível por feature. */
  figure?: "nota";
  /** Cor da linha (default grafite). */
  stroke?: string;
}

export function BlueprintSchematic({
  width = 220,
  figure = "nota",
  stroke = "var(--color-graphite)",
  className,
  ...props
}: BlueprintSchematicProps) {
  const reduced = useReducedMotion();

  const lineProps = (i: number): MotionProps =>
    reduced
      ? { initial: false, animate: { pathLength: 1, opacity: 1 } }
      : {
          initial: { pathLength: 0, opacity: 0.25 },
          whileInView: { pathLength: 1, opacity: 1 },
          viewport: { once: true, margin: "0px 0px -10% 0px" },
          transition: {
            pathLength: { duration: DUR.line, ease: EASE.settle, delay: i * STAGGER },
            opacity: { duration: 0.2, delay: i * STAGGER },
          },
        };

  return (
    <div
      className={cn("inline-block", className)}
      role="img"
      aria-label="Esquemático técnico de uma nota fiscal"
      {...props}
    >
      <svg
        width={width}
        viewBox="0 0 200 260"
        fill="none"
        style={{ display: "block" }}
      >
        <g stroke={stroke} strokeWidth={1.25} strokeLinecap="round" strokeLinejoin="round">
          {/* contorno do documento */}
          <motion.rect x={20} y={14} width={160} height={232} rx={2} {...lineProps(0)} />
          {/* cabeçalho */}
          <motion.line x1={20} y1={56} x2={180} y2={56} {...lineProps(1)} />
          <motion.rect x={32} y={26} width={34} height={20} rx={1} {...lineProps(2)} />
          <motion.line x1={78} y1={30} x2={166} y2={30} {...lineProps(3)} />
          <motion.line x1={78} y1={40} x2={140} y2={40} {...lineProps(4)} />
          {/* linhas de itens */}
          <motion.line x1={32} y1={78} x2={168} y2={78} {...lineProps(5)} />
          <motion.line x1={32} y1={98} x2={168} y2={98} {...lineProps(6)} />
          <motion.line x1={32} y1={118} x2={168} y2={118} {...lineProps(7)} />
          <motion.line x1={32} y1={138} x2={168} y2={138} {...lineProps(8)} />
          {/* coluna de valores */}
          <motion.line x1={132} y1={70} x2={132} y2={146} {...lineProps(9)} />
          {/* bloco de totais */}
          <motion.line x1={20} y1={168} x2={180} y2={168} {...lineProps(10)} />
          <motion.line x1={104} y1={184} x2={168} y2={184} {...lineProps(11)} />
          <motion.line x1={104} y1={200} x2={168} y2={200} {...lineProps(12)} />
        </g>
        {/* selo verde (o acento único) — círculo + check, em verde */}
        <g stroke="var(--color-green)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" fill="none">
          <motion.circle cx={52} cy={208} r={18} {...lineProps(13)} />
          <motion.path d="M44 208 l6 7 l12 -15" {...lineProps(14)} />
        </g>
      </svg>
    </div>
  );
}
