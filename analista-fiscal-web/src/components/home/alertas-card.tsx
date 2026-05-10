"use client";

import Link from "next/link";
import { AlertCircle, ArrowRight, Bell } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";

export function AlertasCard() {
  const { data, isLoading } = useFiscalSaude();
  const alertas = data?.alertasPrioritarios ?? [];

  return (
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Bell className="size-4 text-[var(--color-txt-2)]" />
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Alertas
        </span>
        <Pill tom="neutral">{alertas.length}</Pill>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : alertas.length === 0 ? (
        <p className="text-sm text-[var(--color-txt-2)] py-2">
          Sem alertas — está tudo tranquilo.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {alertas.map((a) => (
            <div
              key={a.id}
              className="rounded-md border p-3 flex items-start gap-2.5"
              style={{
                background:
                  a.tom === "warn"
                    ? "var(--color-amber-d)"
                    : a.tom === "error"
                      ? "var(--color-red-d)"
                      : "var(--color-blue-d)",
                borderColor:
                  a.tom === "warn"
                    ? "rgba(255,184,77,0.22)"
                    : a.tom === "error"
                      ? "rgba(255,85,102,0.22)"
                      : "rgba(77,142,255,0.22)",
              }}
            >
              <AlertCircle
                className="size-4 mt-0.5"
                style={{
                  color:
                    a.tom === "warn"
                      ? "var(--color-amber)"
                      : a.tom === "error"
                        ? "var(--color-red)"
                        : "var(--color-blue)",
                }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-[var(--color-txt)]">{a.titulo}</p>
                <p className="text-xs text-[var(--color-txt-2)] leading-relaxed mt-0.5">
                  {a.descricao}
                </p>
                {a.acao ? (
                  <Link
                    href={a.acao.rota}
                    className="inline-flex items-center gap-1 mt-1.5 text-xs font-bold text-[var(--color-lime)] hover:underline"
                  >
                    {a.acao.label}
                    <ArrowRight className="size-3" />
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
