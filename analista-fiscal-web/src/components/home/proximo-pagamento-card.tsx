"use client";

import Link from "next/link";
import { ArrowRight, CalendarClock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Moeda } from "@/components/shared/moeda";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { formatarDataBR } from "@/lib/format/data";

export function ProximoPagamentoCard() {
  const { data, isLoading } = useApuracaoAtual();

  return (
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <CalendarClock className="size-4 text-[var(--color-blue)]" />
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Próximo pagamento
        </span>
        <Pill tom="info">DAS</Pill>
      </div>
      {isLoading || !data ? (
        <>
          <Skeleton className="h-9 w-44" />
          <Skeleton className="h-4 w-32" />
        </>
      ) : (
        <>
          <p className="mono text-3xl font-bold text-[var(--color-txt)] leading-none">
            <Moeda valor={data.valorDAS} />
          </p>
          <p className="text-sm text-[var(--color-txt-2)]">
            Vence em <span className="mono font-semibold text-[var(--color-txt)]">{formatarDataBR(data.vencimento)}</span>
          </p>
        </>
      )}
      <Button asChild variant="outline" size="sm" className="self-start mt-1">
        <Link href="/fiscal/guias">
          Ver guia
          <ArrowRight className="size-3.5" />
        </Link>
      </Button>
    </Card>
  );
}
