"use client";

import Link from "next/link";
import { ArrowRight, FileSignature } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";
import { formatarDataBR } from "@/lib/format/data";

export function ProximaObrigacaoCard() {
  const { data, isLoading } = useFiscalSaude();
  const obrig = data?.proximaObrigacao;

  return (
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <FileSignature className="size-4 text-[var(--color-amber)]" />
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Próxima obrigação
        </span>
        <Pill tom="warn">declaração</Pill>
      </div>
      {isLoading || !obrig ? (
        <>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </>
      ) : (
        <>
          <p className="text-lg font-bold text-[var(--color-txt)] leading-tight">
            {obrig.titulo}
          </p>
          <p className="text-sm text-[var(--color-txt-2)] leading-relaxed">
            {obrig.descricao}
          </p>
          <p className="text-xs text-[var(--color-txt-3)] mono">
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
    </Card>
  );
}
