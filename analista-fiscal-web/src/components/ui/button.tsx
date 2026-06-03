"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-[background-color,color,border-color] duration-[160ms] ease-[var(--ease-settle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/45 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-paper)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
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
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-[var(--radius-sm)] px-3 text-xs",
        lg: "h-11 rounded-[var(--radius-sm)] px-6 text-base",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
