"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, Bell, XCircle, Info } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";

/** Uma ação por alerta — invariante §7. Ícone + cor + palavra por tom. */
const TOM_MAP = {
  warn: {
    icon: AlertTriangle,
    color: "var(--color-ochre)",
    bg: "color-mix(in srgb, var(--color-ochre) 8%, var(--color-card))",
    border: "color-mix(in srgb, var(--color-ochre) 25%, var(--color-rule))",
  },
  error: {
    icon: XCircle,
    color: "var(--color-danger)",
    bg: "color-mix(in srgb, var(--color-danger) 8%, var(--color-card))",
    border: "color-mix(in srgb, var(--color-danger) 25%, var(--color-rule))",
  },
  info: {
    icon: Info,
    color: "var(--color-ink-2)",
    bg: "var(--color-paper-2)",
    border: "var(--color-rule)",
  },
} as const;

export function AlertasCard() {
  const { data, isLoading } = useFiscalSaude();
  const alertas = data?.alertasPrioritarios ?? [];

  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Bell className="size-4 text-[var(--color-ink-2)]" aria-hidden />
        <Fig n={3} titulo="Alertas" size="sm" />
        <Pill tom="neutral">{alertas.length}</Pill>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : alertas.length === 0 ? (
        <p className="text-sm text-[var(--color-ink-2)] py-2">
          Sem alertas — está tudo em dia.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {alertas.map((a) => {
            const tom = (a.tom in TOM_MAP ? a.tom : "info") as keyof typeof TOM_MAP;
            const cfg = TOM_MAP[tom];
            const Icon = cfg.icon;
            return (
              <div
                key={a.id}
                className="rounded-[var(--radius-md)] border p-3 flex items-start gap-2.5"
                style={{
                  background: cfg.bg,
                  borderColor: cfg.border,
                }}
              >
                <Icon
                  className="size-4 mt-0.5 shrink-0"
                  style={{ color: cfg.color }}
                  aria-hidden
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[var(--color-ink)]">
                    {a.titulo}
                  </p>
                  <p className="text-xs text-[var(--color-ink-2)] leading-relaxed mt-0.5">
                    {a.descricao}
                  </p>
                  {/* uma ação por alerta */}
                  {a.acao ? (
                    <Link
                      href={a.acao.rota}
                      className="inline-flex items-center gap-1 mt-1.5 text-xs font-bold text-[var(--color-green)] hover:underline"
                    >
                      {a.acao.label}
                      <ArrowRight className="size-3" />
                    </Link>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Framed>
  );
}
