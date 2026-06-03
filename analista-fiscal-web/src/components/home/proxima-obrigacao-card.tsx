"use client";

import Link from "next/link";
import { ArrowRight, FileSignature } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";
import { formatarDataBR } from "@/lib/format/data";

export function ProximaObrigacaoCard() {
  const { data, isLoading } = useFiscalSaude();
  const obrig = data?.proximaObrigacao;

  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <FileSignature className="size-4 text-[var(--color-ochre)]" aria-hidden />
        <Fig n={2} titulo="Próxima obrigação" size="sm" />
        <Pill tom="warn">declaração</Pill>
      </div>
      {isLoading || !obrig ? (
        <>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </>
      ) : (
        <>
          <p className="text-lg font-semibold text-[var(--color-ink)] leading-tight">
            {obrig.titulo}
          </p>
          <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
            {obrig.descricao}
          </p>
          <p
            className="text-xs text-[var(--color-ink-3)] mono"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            até {formatarDataBR(obrig.vencimento)}
          </p>
        </>
      )}
      {obrig ? (
        <Button asChild variant="outline" size="sm" className="self-start mt-1">
          <Link href={obrig.acao.rota}>
            {obrig.acao.label}
            <ArrowRight className="size-3.5" />
          </Link>
        </Button>
      ) : null}
    </Framed>
  );
}
