import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] mono",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-lime-d)] text-[var(--color-lime)] border-[rgba(163,255,107,0.22)]",
        secondary:
          "bg-[var(--color-blue-d)] text-[var(--color-blue)] border-[rgba(77,142,255,0.22)]",
        warn: "bg-[var(--color-amber-d)] text-[var(--color-amber)] border-[rgba(255,184,77,0.22)]",
        destructive:
          "bg-[var(--color-red-d)] text-[var(--color-red)] border-[rgba(255,85,102,0.22)]",
        outline:
          "bg-transparent text-[var(--color-txt-2)] border-[var(--color-line-2)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
