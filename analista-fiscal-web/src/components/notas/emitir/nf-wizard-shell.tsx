"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Passo {
  numero: number;
  titulo: string;
}

interface Props {
  passos: Passo[];
  passoAtual: number;
  children: React.ReactNode;
}

export function NfWizardShell({ passos, passoAtual, children }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {passos.map((p, i) => {
          const concluido = p.numero < passoAtual;
          const atual = p.numero === passoAtual;
          return (
            <React.Fragment key={p.numero}>
              <div className="flex items-center gap-2 shrink-0">
                <div
                  className={cn(
                    "size-7 rounded-full grid place-items-center text-[12px] font-bold mono transition-colors",
                    concluido
                      ? "bg-[var(--color-lime)] text-[#06080f]"
                      : atual
                        ? "bg-[var(--color-lime-d)] text-[var(--color-lime)] border border-[rgba(163,255,107,0.32)]"
                        : "bg-[var(--color-card-2)] text-[var(--color-txt-3)] border border-[var(--color-line-2)]"
                  )}
                >
                  {concluido ? <Check className="size-3.5" /> : p.numero}
                </div>
                <span
                  className={cn(
                    "text-[12px] font-semibold uppercase tracking-[0.12em]",
                    atual
                      ? "text-[var(--color-txt)]"
                      : concluido
                        ? "text-[var(--color-txt-2)]"
                        : "text-[var(--color-txt-3)]"
                  )}
                >
                  {p.titulo}
                </span>
              </div>
              {i < passos.length - 1 ? (
                <div
                  className={cn(
                    "h-px flex-1 min-w-[24px]",
                    concluido
                      ? "bg-[var(--color-lime)]"
                      : "bg-[var(--color-line-2)]"
                  )}
                />
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
      {children}
    </div>
  );
}
