import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Fig — rótulo técnico que numera uma seção como num documento de engenharia:
 *   FIG. 02 — PARECER FISCAL
 * Mono, caixa-alta, tracking aberto; o número fica em tinta cheia e o traço/título
 * em ink-2. Use como cabeçalho de blocos para dar a personalidade "blueprint".
 */
interface FigProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Número da figura (será zero-paddeado para 2 dígitos). */
  n: number | string;
  /** Título da figura (caixa-alta aplicada por CSS). */
  titulo?: React.ReactNode;
  /** Tamanho do rótulo. */
  size?: "sm" | "md";
}

function pad(n: number | string) {
  const s = String(n);
  return s.length === 1 ? `0${s}` : s;
}

const Fig = React.forwardRef<HTMLDivElement, FigProps>(
  ({ n, titulo, size = "md", className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "mono flex items-center gap-2 uppercase tracking-[0.18em] text-[var(--color-ink-2)]",
        size === "sm" ? "text-[10px]" : "text-[11px]",
        className
      )}
      {...props}
    >
      <span className="font-semibold text-[var(--color-ink)]">Fig. {pad(n)}</span>
      {titulo ? (
        <>
          <span aria-hidden className="text-[var(--color-graphite)]">
            —
          </span>
          <span>{titulo}</span>
        </>
      ) : null}
    </div>
  )
);
Fig.displayName = "Fig";

export { Fig };
