"use client";

import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="light"
      richColors={false}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-[var(--color-card)] group-[.toaster]:text-[var(--color-ink)] group-[.toaster]:border group-[.toaster]:border-[var(--color-ink)] group-[.toaster]:rounded-[var(--radius-md)]",
          description: "group-[.toast]:text-[var(--color-ink-2)]",
          actionButton:
            "group-[.toast]:bg-[var(--color-green)] group-[.toast]:text-[var(--color-paper)]",
          cancelButton:
            "group-[.toast]:bg-[var(--color-paper-2)] group-[.toast]:text-[var(--color-ink-2)]",
        },
      }}
      {...props}
    />
  );
}
