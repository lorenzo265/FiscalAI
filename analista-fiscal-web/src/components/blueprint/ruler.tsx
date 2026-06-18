"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { EASE } from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/**
 * Ruler — régua de medição com ticks. Divisor técnico que substitui o
 * `<Separator/>` genérico quando se quer reforçar a personalidade "instrumento".
 * Horizontal (default) ou vertical; ticks maiores a cada `majorEvery`.
 *
 * Puro CSS (repeating-linear-gradient) — sem dependência de tamanho fixo; o tick
 * acompanha a largura/altura do container.
 *
 * ATENÇÃO: este componente é consumido como DIVISOR em ~46 telas (`<Ruler />`).
 * A API e o visual do divisor permanecem INTOCADOS. A "régua de limites"
 * (assinatura nº 2 da v2) é o componente IRMÃO `RulerGauge` abaixo — aditivo,
 * sem quebrar nenhum call-site existente.
 */
interface RulerProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
  /** Espaçamento entre ticks (px). */
  gap?: number;
  /** A cada quantos ticks vem um tick maior. */
  majorEvery?: number;
  /** Altura dos ticks menores (px). */
  tick?: number;
}

const Ruler = React.forwardRef<HTMLDivElement, RulerProps>(
  (
    { orientation = "horizontal", gap = 8, majorEvery = 5, tick = 4, className, style, ...props },
    ref
  ) => {
    const major = tick * 2;
    const isH = orientation === "horizontal";
    const line = "var(--color-rule)";
    const tickColor = "var(--color-rule-2)";

    // baseline fio + ticks via gradientes
    const axis = isH ? "to right" : "to bottom";

    return (
      <div
        ref={ref}
        aria-hidden="true"
        className={cn("relative shrink-0", isH ? "w-full" : "h-full", className)}
        style={{
          ...(isH ? { height: major } : { width: major }),
          backgroundImage: [
            // fio base na ponta
            `linear-gradient(${isH ? "to bottom" : "to right"}, ${line} 1px, transparent 1px)`,
            // ticks menores
            `repeating-linear-gradient(${axis}, ${tickColor} 0 1px, transparent 1px ${gap}px)`,
            // ticks maiores
            `repeating-linear-gradient(${axis}, ${tickColor} 0 1px, transparent 1px ${gap * majorEvery}px)`,
          ].join(", "),
          backgroundRepeat: "no-repeat, repeat, repeat",
          backgroundSize: isH
            ? `100% 1px, ${tick}px ${tick}px, ${tick}px ${major}px`
            : `1px 100%, ${tick}px ${tick}px, ${major}px ${tick}px`,
          backgroundPosition: isH ? "top, top, top" : "left, left, left",
          ...style,
        }}
        {...props}
      />
    );
  }
);
Ruler.displayName = "Ruler";

/* ─────────────────────────────────────────────────────────────────────────
 * RulerGauge — a "régua de limites": assinatura nº 2 da identidade v2 (§3).
 * Régua horizontal com ticks mono, preenchimento verde do progresso (desenha
 * da esquerda, scaleX 800ms reveal) e um marcador de PROJEÇÃO ("no seu ritmo:
 * outubro") que pulsa 1×. Base dos monitores de limite (Plano §5, ferramenta 09
 * — ex.: teto do Simples Nacional).
 *
 * Motion §4: honra `prefers-reduced-motion` (troca seca — preenchimento já cheio,
 * sem pulso). Anima só `transform`/`opacity`. 1 assinatura por tela.
 * ──────────────────────────────────────────────────────────────────────── */

export interface RulerGaugeProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Valor acumulado atual (ex.: receita no ano). */
  valor: number;
  /** Limite/teto (ex.: teto do Simples). 100% do preenchimento. */
  limite: number;
  /**
   * Projeção opcional: ponto na régua onde o ritmo atual cruza algum marco
   * (em mesma unidade de `valor`/`limite`). Ex.: receita projetada p/ dezembro.
   */
  projecao?: number;
  /** Rótulo curto da projeção (ex.: "no seu ritmo: outubro"). */
  projecaoLabel?: string;
  /** Rótulo à esquerda (ex.: "Teto do Simples"). */
  label?: string;
  /** Texto/nó à direita, em mono (ex.: "73% usado"). */
  valorLabel?: React.ReactNode;
  /** Número de ticks na régua (default 10). */
  ticks?: number;
}

function clampPct(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

const RulerGauge = React.forwardRef<HTMLDivElement, RulerGaugeProps>(
  (
    {
      valor,
      limite,
      projecao,
      projecaoLabel,
      label,
      valorLabel,
      ticks = 10,
      className,
      ...props
    },
    ref
  ) => {
    const reduced = useReducedMotion();

    const pct = clampPct(limite > 0 ? (valor / limite) * 100 : 0);
    const projPct =
      projecao != null && limite > 0 ? clampPct((projecao / limite) * 100) : null;

    // Estoura o limite? o preenchimento vira danger (sem virar 2º acento de
    // marca: danger é "mundo quente", não acento cromático).
    const estourou = pct >= 100 || (projPct != null && projPct >= 100);
    const fill = estourou ? "var(--color-danger)" : "var(--color-green)";

    return (
      <div ref={ref} className={cn("flex flex-col gap-1.5", className)} {...props}>
        {(label || valorLabel) && (
          <div className="flex items-baseline justify-between gap-2">
            {label ? (
              <span className="mono text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-ink-2)]">
                {label}
              </span>
            ) : (
              <span />
            )}
            {valorLabel ? (
              <span className="mono text-[11px] tabular-nums text-[var(--color-ink)]">
                {valorLabel}
              </span>
            ) : null}
          </div>
        )}

        {/* trilho */}
        <div
          className="relative h-2.5 w-full overflow-hidden rounded-[var(--radius-sm)]"
          style={{ background: "var(--color-paper-2)", border: "1px solid var(--color-rule)" }}
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
          aria-label={label ?? "Uso do limite"}
        >
          {/* ticks mono (decorativos) */}
          <div
            aria-hidden="true"
            className="absolute inset-0"
            style={{
              backgroundImage: `repeating-linear-gradient(to right, var(--color-rule-2) 0 1px, transparent 1px ${100 / ticks}%)`,
            }}
          />
          {/* preenchimento — desenha da esquerda (scaleX 0→pct), 800ms reveal */}
          <motion.div
            className="absolute inset-y-0 left-0 origin-left"
            style={{ width: `${pct}%`, background: fill }}
            initial={reduced ? false : { scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={reduced ? { duration: 0 } : { duration: 0.8, ease: EASE.reveal }}
          />
        </div>

        {/* marcador de projeção — pulsa 1× ao revelar */}
        {projPct != null ? (
          <div className="relative h-4">
            <motion.div
              className="absolute top-0 flex -translate-x-1/2 flex-col items-center"
              style={{ left: `${projPct}%` }}
              initial={reduced ? false : { opacity: 0 }}
              animate={
                reduced
                  ? { opacity: 1 }
                  : { opacity: [0, 1, 0.55, 1] }
              }
              transition={
                reduced ? { duration: 0 } : { duration: 0.9, ease: EASE.settle, delay: 0.8 }
              }
            >
              <span
                aria-hidden="true"
                className="h-2 w-px"
                style={{ background: estourou ? "var(--color-danger)" : "var(--color-ink-2)" }}
              />
              {projecaoLabel ? (
                <span className="mono whitespace-nowrap text-[9px] uppercase tracking-[0.1em] text-[var(--color-ink-2)]">
                  {projecaoLabel}
                </span>
              ) : null}
            </motion.div>
          </div>
        ) : null}
      </div>
    );
  }
);
RulerGauge.displayName = "RulerGauge";

export { Ruler, RulerGauge };
