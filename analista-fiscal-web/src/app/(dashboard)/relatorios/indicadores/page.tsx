"use client";

import dynamic from "next/dynamic";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useIndicadores } from "@/hooks/use-relatorios";

const Sparkline = dynamic(
  () =>
    import("@/components/relatorios/sparkline").then((m) => ({
      default: m.Sparkline,
    })),
  { ssr: false, loading: () => <Skeleton className="h-12 w-full" /> }
);
import { formatarMoeda } from "@/lib/format/moeda";
import type { Indicador } from "@/lib/schemas/relatorios";
import { cn } from "@/lib/utils";

const COR_POR_TOM: Record<Indicador["tom"], string> = {
  ok: "var(--color-lime)",
  warn: "var(--color-amber)",
  error: "var(--color-red)",
  neutral: "var(--color-blue)",
};

export default function IndicadoresPage() {
  const { data, isLoading, isError, refetch } = useIndicadores();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Relatórios · Indicadores
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Indicadores financeiros
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          A saúde financeira em 8 números. Cada card mostra a evolução nos
          últimos 12 meses pra você ver tendência, não só o valor de hoje.
        </p>
      </header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando indicadores..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {data.map((ind) => (
            <CardIndicador key={ind.chave} indicador={ind} />
          ))}
        </div>
      )}
    </div>
  );
}

function CardIndicador({ indicador }: { indicador: Indicador }) {
  const cor = COR_POR_TOM[indicador.tom];
  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)] truncate">
            {indicador.titulo}
          </p>
          <p className="text-[11px] text-[var(--color-txt-2)] mt-1 line-clamp-2">
            {indicador.descricao}
          </p>
        </div>
        <PillTom tom={indicador.tom} />
      </div>

      <p className="mono text-2xl font-bold text-[var(--color-txt)] leading-tight">
        {formatarValor(indicador)}
      </p>

      <Variacao indicador={indicador} />

      <Sparkline serie={indicador.serie} cor={cor} formato={indicador.formato} />
    </Card>
  );
}

function PillTom({ tom }: { tom: Indicador["tom"] }) {
  const label = {
    ok: "saudável",
    warn: "atenção",
    error: "crítico",
    neutral: "—",
  } as const;
  return <Pill tom={tom}>{label[tom]}</Pill>;
}

function Variacao({ indicador }: { indicador: Indicador }) {
  if (indicador.direcao === "estavel") {
    return (
      <span className="flex items-center gap-1 text-[11px] text-[var(--color-txt-3)]">
        <Minus className="size-3" /> estável vs mês anterior
      </span>
    );
  }
  const Icon = indicador.direcao === "alta" ? TrendingUp : TrendingDown;
  const positivo = indicador.direcao === "alta";
  const cor = positivo ? "var(--color-lime)" : "var(--color-red)";
  return (
    <span
      className={cn("flex items-center gap-1 text-[11px] mono")}
      style={{ color: cor }}
    >
      <Icon className="size-3" />
      {(indicador.variacao >= 0 ? "+" : "") + indicador.variacao.toFixed(1).replace(".", ",")}%
      <span className="text-[var(--color-txt-3)]">vs mês anterior</span>
    </span>
  );
}

function formatarValor(ind: Indicador): string {
  switch (ind.formato) {
    case "moeda":
      return formatarMoeda(ind.valor);
    case "percentual":
      return `${ind.valor.toFixed(1).replace(".", ",")}%`;
    case "dias":
      return `${Math.round(ind.valor)} dias`;
    case "decimal":
      return ind.valor.toFixed(2).replace(".", ",");
  }
}
