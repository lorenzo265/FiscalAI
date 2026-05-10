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
          "flex h-9 w-full rounded-md border bg-[var(--color-card-2)] px-3 py-1 text-sm text-[var(--color-txt)] placeholder:text-[var(--color-txt-3)] transition-colors",
          "border-[var(--color-line-2)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-lime)]/30 focus-visible:border-[var(--color-lime)]/50",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
