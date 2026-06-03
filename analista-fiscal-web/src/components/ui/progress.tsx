"use client";

import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

/**
 * Tons canônicos Arkan: `green` (saúde/acento), `ochre` (atenção),
 * `danger` (erro), `neutral` (tinta). Os nomes legados
 * (`lime|amber|red|blue`) seguem aceitos como aliases para não quebrar
 * callers antigos — mapeiam para os canônicos.
 */
type ProgressTom =
  | "green"
  | "ochre"
  | "danger"
  | "neutral"
  // aliases legados
  | "lime"
  | "amber"
  | "red"
  | "blue";

interface ProgressProps
  extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
  tom?: ProgressTom;
}

const tonsMap: Record<ProgressTom, string> = {
  green: "bg-[var(--color-green)]",
  ochre: "bg-[var(--color-ochre)]",
  danger: "bg-[var(--color-danger)]",
  neutral: "bg-[var(--color-ink-2)]",
  // aliases legados → canônicos
  lime: "bg-[var(--color-green)]",
  amber: "bg-[var(--color-ochre)]",
  red: "bg-[var(--color-danger)]",
  blue: "bg-[var(--color-ink-2)]",
};

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  ProgressProps
>(({ className, value, tom = "green", ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-1.5 w-full overflow-hidden rounded-[var(--radius-sm)] bg-[var(--color-rule)]",
      className
    )}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className={cn("h-full w-full flex-1 transition-all", tonsMap[tom])}
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
