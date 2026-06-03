import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-[var(--radius-sm)] border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] mono",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-green-wash)] text-[var(--color-green-deep)] border-[var(--color-green)]/30",
        secondary:
          "bg-[var(--color-paper-2)] text-[var(--color-ink-2)] border-[var(--color-rule-2)]",
        warn: "bg-[var(--color-paper-2)] text-[var(--color-ochre)] border-[var(--color-ochre)]/35",
        destructive:
          "bg-[var(--color-paper-2)] text-[var(--color-danger)] border-[var(--color-danger)]/35",
        outline:
          "bg-transparent text-[var(--color-ink-2)] border-[var(--color-rule-2)]",
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
