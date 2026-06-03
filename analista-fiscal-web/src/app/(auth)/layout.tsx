import type { ReactNode } from "react";
import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
      style={{ background: "var(--color-paper)" }}
    >
      <div className="flex items-center gap-2.5 mb-8">
        <Logo size={30} />
        <div className="flex flex-col leading-none">
          <span className="font-[family-name:var(--font-serif)] text-[20px] font-semibold tracking-tight text-[var(--color-ink)]">
            Arkan
          </span>
          <span className="mono text-[9px] uppercase tracking-[0.22em] text-[var(--color-ink-3)]">
            Fiscal · Instrumento
          </span>
        </div>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
