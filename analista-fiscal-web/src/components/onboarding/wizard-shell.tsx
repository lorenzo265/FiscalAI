"use client";

import * as React from "react";
import { Logo } from "@/components/layout/logo";
import { useOnboardingStore, ONBOARDING_TOTAL_PASSOS } from "@/lib/stores/onboarding-store";
import { cn } from "@/lib/utils";

const TITULOS: Record<number, { titulo: string; subtitulo: string }> = {
  1: { titulo: "Vamos achar sua empresa", subtitulo: "Comece pelo CNPJ — buscamos o resto." },
  2: { titulo: "Como você é tributado?", subtitulo: "Isso define quais módulos você usa." },
  3: { titulo: "Certificado digital A1", subtitulo: "É o que permite emitir nota fiscal." },
  4: { titulo: "Conecte suas contas", subtitulo: "Conciliação automática via Open Finance." },
  5: { titulo: "Tudo pronto", subtitulo: "Confira o resumo e entre no painel." },
};

export function WizardShell({ children }: { children: React.ReactNode }) {
  const passo = useOnboardingStore((s) => s.passo);
  const meta = TITULOS[passo] ?? TITULOS[1]!;

  return (
    <div className="w-full max-w-[760px] flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Logo size={36} />
        <div className="leading-tight">
          <p className="text-sm font-semibold text-[var(--color-txt)]">FiscalAI</p>
          <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-txt-3)] mono">
            Onboarding · passo {passo} de {ONBOARDING_TOTAL_PASSOS}
          </p>
        </div>
      </div>

      <ProgressBar passo={passo} total={ONBOARDING_TOTAL_PASSOS} />

      <div
        className="rounded-[14px] border p-7 md:p-9 shadow-2xl"
        style={{
          background: "var(--color-card)",
          borderColor: "var(--color-line-2)",
        }}
      >
        <div className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-txt)]">
            {meta.titulo}
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] mt-1">{meta.subtitulo}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

function ProgressBar({ passo, total }: { passo: number; total: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }, (_, i) => i + 1).map((n) => {
        const ativo = n <= passo;
        const atual = n === passo;
        return (
          <div
            key={n}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors",
              ativo
                ? "bg-[var(--color-lime)]"
                : "bg-[var(--color-card-3)]",
              atual ? "shadow-[0_0_12px_rgba(163,255,107,0.4)]" : ""
            )}
          />
        );
      })}
    </div>
  );
}
