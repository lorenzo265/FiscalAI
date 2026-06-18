"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/**
 * Button — primitiva Arkan "Claro" v2 (identidade-v2 §3).
 *  - Primário: verde sólido, radius 10 (`--radius-md`), altura 44px (mobile-first;
 *    resolve o aviso de a11y da Fase 2 e ancora "1 ação primária por tela").
 *  - Press: scale .97 com spring(420,30) — global nas primitivas interativas (§4),
 *    com troca seca sob `prefers-reduced-motion`.
 *  - Ícone opcional à esquerda já suportado: `<Button><Icon/> Texto</Button>`.
 *  - API preservada: variantes (default/secondary/ghost/outline/destructive/link),
 *    sizes (default/sm/lg/icon), `asChild`, e o export `buttonVariants`.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] text-sm font-medium transition-[background-color,color,border-color] duration-[160ms] ease-[var(--ease-settle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/45 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-paper)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-green)] text-[var(--color-paper)] hover:bg-[var(--color-green-deep)] font-semibold",
        secondary:
          "bg-[var(--color-paper-2)] text-[var(--color-ink)] border border-[var(--color-rule-2)] hover:bg-[var(--color-rule)]",
        ghost:
          "text-[var(--color-ink-2)] hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)]",
        outline:
          "border border-[var(--color-ink)] bg-transparent text-[var(--color-ink)] hover:bg-[var(--color-paper-2)]",
        destructive:
          "bg-[var(--color-danger)] text-[var(--color-paper)] hover:brightness-95 font-semibold",
        link: "text-[var(--color-green)] underline-offset-4 decoration-1 hover:underline",
      },
      size: {
        // v2: 44px é a altura-base (toque confortável; "ação primária por tela").
        default: "h-11 px-4 py-2",
        sm: "h-9 rounded-[var(--radius-sm)] px-3 text-xs",
        lg: "h-12 rounded-[var(--radius-md)] px-6 text-base",
        icon: "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

/**
 * Props nativas de button MENOS as que colidem em tipo com o Framer Motion
 * (handlers de drag/animação). Mantém a API pública estável: nenhum call-site
 * usa esses handlers num <Button>, e o `asChild` continua aceitando tudo.
 */
type ConflictingMotionProps =
  | "onDrag"
  | "onDragStart"
  | "onDragEnd"
  | "onDragEnter"
  | "onDragExit"
  | "onDragLeave"
  | "onDragOver"
  | "onDrop"
  | "onAnimationStart"
  | "onAnimationEnd"
  | "onAnimationIteration";

export interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, ConflictingMotionProps>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

/** Spring do press global (§4 motion v2). */
const PRESS_SPRING = { type: "spring" as const, stiffness: 420, damping: 30 };

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, disabled, ...props }, ref) => {
    const reduced = useReducedMotion();

    // `asChild` continua delegando ao filho (Slot) — sem motion, para não
    // forçar props de animação em elementos arbitrários (ex.: <Link>).
    if (asChild) {
      return (
        <Slot
          className={cn(buttonVariants({ variant, size, className }))}
          ref={ref}
          {...props}
        />
      );
    }

    // Press scale .97 com spring; troca seca sob reduced-motion.
    const motionProps: HTMLMotionProps<"button"> =
      reduced || disabled ? {} : { whileTap: { scale: 0.97 }, transition: PRESS_SPRING };

    return (
      <motion.button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled}
        {...motionProps}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
