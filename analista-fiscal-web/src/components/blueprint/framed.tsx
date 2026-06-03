import * as React from "react";
import { cn } from "@/lib/utils";
import { CropMarks } from "./crop-marks";

/**
 * Framed — o painel-base da linguagem Arkan: borda 1px tinta + crop marks nos
 * cantos (registro técnico), cantos quase-retos (radius 2px), fundo papel/card.
 * Substitui o "card flutuante com sombra" pelo "documento emoldurado". Sem
 * sombra suave genérica; a elevação é a moldura, não o blur.
 */
interface FramedProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Mostra as marcas de registro nos cantos (default: true). */
  marks?: boolean;
  /** Borda em tinta cheia (default) ou fio claro (`rule`). */
  tone?: "ink" | "rule";
  /** Fundo do painel. */
  surface?: "card" | "paper" | "paper-2";
  /** Padding interno padronizado. */
  padded?: boolean;
}

const surfaceMap = {
  card: "bg-[var(--color-card)]",
  paper: "bg-[var(--color-paper)]",
  "paper-2": "bg-[var(--color-paper-2)]",
} as const;

const Framed = React.forwardRef<HTMLDivElement, FramedProps>(
  (
    {
      className,
      children,
      marks = true,
      tone = "ink",
      surface = "card",
      padded = true,
      ...props
    },
    ref
  ) => (
    <div
      ref={ref}
      className={cn(
        "relative rounded-[var(--radius-md)] border text-[var(--color-ink)]",
        tone === "ink" ? "border-[var(--color-ink)]" : "border-[var(--color-rule)]",
        surfaceMap[surface],
        padded && "p-5",
        className
      )}
      {...props}
    >
      {marks ? <CropMarks /> : null}
      {children}
    </div>
  )
);
Framed.displayName = "Framed";

export { Framed };
