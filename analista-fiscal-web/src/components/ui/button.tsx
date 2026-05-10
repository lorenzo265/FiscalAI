"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-lime)]/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-lime)] text-[#06080f] hover:bg-[var(--color-lime)]/90 font-semibold",
        secondary:
          "bg-[var(--color-blue-d)] text-[var(--color-blue)] border border-[rgba(77,142,255,0.22)] hover:bg-[var(--color-blue-d)]/80",
        ghost:
          "text-[var(--color-txt-2)] hover:bg-[var(--color-card-2)] hover:text-[var(--color-txt)]",
        outline:
          "border border-[var(--color-line-2)] bg-[var(--color-card)] text-[var(--color-txt)] hover:bg-[var(--color-card-2)]",
        destructive:
          "bg-[var(--color-red)] text-white hover:bg-[var(--color-red)]/90 font-semibold",
        link: "text-[var(--color-blue)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-md px-6 text-base",
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
