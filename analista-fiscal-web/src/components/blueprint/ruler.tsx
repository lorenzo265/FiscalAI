import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Ruler — régua de medição com ticks. Divisor técnico que substitui o
 * `<Separator/>` genérico quando se quer reforçar a personalidade "instrumento".
 * Horizontal (default) ou vertical; ticks maiores a cada `majorEvery`.
 *
 * Puro CSS (repeating-linear-gradient) — sem dependência de tamanho fixo; o tick
 * acompanha a largura/altura do container.
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

export { Ruler };
