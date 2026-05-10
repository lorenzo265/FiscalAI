"use client";

import Link from "next/link";
import { ArrowRight, AlertTriangle, CheckCircle2, AlertOctagon } from "lucide-react";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const TOM_PALETA: Record<"ok" | "warn" | "error", { color: string; bg: string; tomPill: PillTom }> = {
  ok: { color: "var(--color-lime)", bg: "var(--color-lime-d)", tomPill: "ok" },
  warn: { color: "var(--color-amber)", bg: "var(--color-amber-d)", tomPill: "warn" },
  error: { color: "var(--color-red)", bg: "var(--color-red-d)", tomPill: "error" },
};

export function FiscalHealthScore() {
  const { data, isLoading, isError, refetch } = useFiscalSaude();

  if (isLoading) return <LoadingState titulo="Calculando seu Fiscal Health Score..." />;
  if (isError || !data) {
    return <ErrorState onTentarNovamente={() => void refetch()} />;
  }

  const paleta = TOM_PALETA[data.tom];
  const Icon = data.tom === "ok" ? CheckCircle2 : data.tom === "warn" ? AlertTriangle : AlertOctagon;

  return (
    <section
      className="rounded-[14px] border p-6 md:p-7 flex flex-col md:flex-row items-start md:items-center gap-6"
      style={{
        background: "var(--color-card)",
        borderColor: "var(--color-line-2)",
      }}
    >
      <div className="flex items-center gap-5 md:gap-6">
        <div
          className="size-24 rounded-2xl grid place-items-center"
          style={{ background: paleta.bg }}
        >
          <span
            className="mono font-extrabold leading-none"
            style={{ color: paleta.color, fontSize: "44px" }}
          >
            {data.score}
          </span>
        </div>
        <div className="flex flex-col gap-1.5">
          <Pill tom={paleta.tomPill}>
            <Icon className="size-3 inline mr-1" />
            Fiscal Health Score
          </Pill>
          <h2
            className={cn(
              "text-2xl md:text-[28px] font-extrabold tracking-tight leading-tight",
              "text-[var(--color-txt)]"
            )}
          >
            {data.titulo}
          </h2>
          <p className="text-sm text-[var(--color-txt-2)] max-w-md leading-relaxed">
            {data.descricao}
          </p>
          <div className="mt-1 max-w-sm">
            <Progress value={data.score} tom={data.tom === "ok" ? "lime" : data.tom === "warn" ? "amber" : "red"} />
          </div>
        </div>
      </div>

      <div className="flex-1" />

      <div className="grid grid-cols-3 gap-2 w-full md:w-auto md:max-w-[400px]">
        {data.componentes.slice(0, 6).map((c) => (
          <ComponenteMini key={c.categoria} label={c.label} pontuacao={c.pontuacao} tom={c.tom} />
        ))}
      </div>

      {data.alertasPrioritarios[0]?.acao ? (
        <Button asChild variant="outline" size="sm" className="hidden md:flex">
          <Link href={data.alertasPrioritarios[0].acao.rota}>
            {data.alertasPrioritarios[0].acao.label}
            <ArrowRight className="size-3.5" />
          </Link>
        </Button>
      ) : null}
    </section>
  );
}

function ComponenteMini({
  label,
  pontuacao,
  tom,
}: {
  label: string;
  pontuacao: number;
  tom: "ok" | "warn" | "error";
}) {
  const cor = TOM_PALETA[tom].color;
  return (
    <div
      className="rounded-md p-2 border flex flex-col gap-0.5"
      style={{
        background: "var(--color-card-2)",
        borderColor: "var(--color-line-2)",
      }}
    >
      <span className="text-[9px] uppercase tracking-[0.12em] font-bold text-[var(--color-txt-3)] truncate">
        {label}
      </span>
      <span className="mono text-sm font-bold" style={{ color: cor }}>
        {pontuacao}
        <span className="text-[var(--color-txt-3)] text-[10px] ml-0.5">/100</span>
      </span>
    </div>
  );
}
