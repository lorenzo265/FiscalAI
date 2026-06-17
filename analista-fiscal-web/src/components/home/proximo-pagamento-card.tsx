"use client";

import Link from "next/link";
import { ArrowRight, CalendarClock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { formatarDataBR } from "@/lib/format/data";
import { OBRIGACOES } from "@/lib/traducao/obrigacoes";
import { classificarUrgencia } from "@/lib/urgencia";

export function ProximoPagamentoCard() {
  const { data, isLoading } = useApuracaoAtual();
  const urg = data ? classificarUrgencia(data.vencimento) : null;

  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <CalendarClock className="size-4 text-[var(--color-ink-2)]" aria-hidden />
        <Fig n={1} titulo="Próximo pagamento" size="sm" />
        {/* sigla técnica em abbr — nunca exposta crua */}
        <Pill tom="neutral" semIcone>
          <abbr title={OBRIGACOES.DAS.termoTecnico} className="no-underline">
            {OBRIGACOES.DAS.termoTecnico}
          </abbr>
        </Pill>
      </div>
      {isLoading || !data ? (
        <>
          <Skeleton className="h-9 w-44" />
          <Skeleton className="h-4 w-32" />
        </>
      ) : (
        <>
          {/* título PT claro */}
          <p className="text-xs text-[var(--color-ink-3)]">
            {OBRIGACOES.DAS.titulo}
          </p>
          <p
            className="mono text-3xl font-bold text-[var(--color-ink)] leading-none"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={data.valorDAS} />
          </p>
          <p className="text-sm leading-snug"
             style={{ color: urg && urg.nivel !== "neutro" ? (urg.nivel === "danger" ? "var(--color-danger)" : "var(--color-ochre)") : "var(--color-ink-2)" }}>
            Vence em{" "}
            <span
              className="mono font-semibold text-[var(--color-ink)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatarDataBR(data.vencimento)}
            </span>
            {urg && urg.nivel !== "neutro" ? (
              <> · <span className="font-bold">{urg.rotulo}</span></>
            ) : null}
          </p>
        </>
      )}
      <Button asChild variant="outline" size="sm" className="self-start mt-1">
        <Link href="/fiscal/guias">
          Ver guia
          <ArrowRight className="size-3.5" />
        </Link>
      </Button>
    </Framed>
  );
}
