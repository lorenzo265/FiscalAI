"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "flex h-9 w-full rounded-[var(--radius-sm)] border bg-[var(--color-paper)] px-3 py-1 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-ink-3)] transition-colors",
          "border-[var(--color-rule-2)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/35 focus-visible:border-[var(--color-green)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-[var(--color-ink)]",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
