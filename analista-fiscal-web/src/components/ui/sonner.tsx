"use client";

import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      richColors={false}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-[var(--color-card)] group-[.toaster]:text-[var(--color-txt)] group-[.toaster]:border-[var(--color-line-2)] group-[.toaster]:shadow-lg group-[.toaster]:rounded-md",
          description: "group-[.toast]:text-[var(--color-txt-2)]",
          actionButton:
            "group-[.toast]:bg-[var(--color-lime)] group-[.toast]:text-[#06080f]",
          cancelButton:
            "group-[.toast]:bg-[var(--color-card-2)] group-[.toast]:text-[var(--color-txt-2)]",
        },
      }}
      {...props}
    />
  );
}
