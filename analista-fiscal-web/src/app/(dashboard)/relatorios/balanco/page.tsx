"use client";

import * as React from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useBalanco } from "@/hooks/use-relatorios";
import { formatarMesAnoBR } from "@/lib/format/data";
import type { LinhaBalanco } from "@/lib/schemas/relatorios";
import { cn } from "@/lib/utils";

export default function BalancoPage() {
  const { data, isLoading, isError, refetch } = useBalanco();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Relatórios · Balanço Patrimonial
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Balanço Patrimonial
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Tudo que a empresa tem (Ativo) precisa ser igual ao que a empresa
          deve mais o capital próprio (Passivo + PL). Aqui mostramos os dois
          lados lado a lado.
        </p>
      </header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Montando balanço..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <BannerEquilibrio
            bate={data.bate}
            diferenca={data.diferenca}
            competencia={data.competencia}
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <Card className="overflow-hidden">
              <Cabecalho titulo="Ativo" total={data.totalAtivo} tom="ok" />
              <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
                {data.ativo.map((l) => (
                  <LinhaItem key={l.codigo} linha={l} />
                ))}
              </ul>
            </Card>

            <Card className="overflow-hidden">
              <Cabecalho
                titulo="Passivo + Patrimônio Líquido"
                total={data.totalPassivo + data.totalPl}
                tom="info"
              />
              <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
                {data.passivoEPl.map((l) => (
                  <LinhaItem key={l.codigo} linha={l} />
                ))}
                <li className="grid grid-cols-[1fr_auto] gap-3 px-5 py-3 bg-[var(--color-card-2)] border-t-2 mt-1"
                  style={{ borderColor: "var(--color-line-2)" }}
                >
                  <span className="text-sm font-bold text-[var(--color-txt)]">
                    Total Passivo + PL
                  </span>
                  <span className="mono text-sm font-bold text-[var(--color-txt)] text-right">
                    <Moeda valor={data.totalPassivo + data.totalPl} />
                  </span>
                </li>
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function BannerEquilibrio({
  bate,
  diferenca,
  competencia,
}: {
  bate: boolean;
  diferenca: number;
  competencia: string;
}) {
  if (bate) {
    return (
      <Alert variant="ok" className="flex items-start gap-3">
        <CheckCircle2 className="size-4 mt-0.5" />
        <div>
          <AlertTitle>
            Balanço fechado em {formatarMesAnoBR(`${competencia}-01`)}
          </AlertTitle>
          <AlertDescription>
            Ativo = Passivo + Patrimônio Líquido. Os números batem.
          </AlertDescription>
        </div>
      </Alert>
    );
  }
  return (
    <Alert variant="destructive" className="flex items-start gap-3">
      <AlertTriangle className="size-4 mt-0.5" />
      <div>
        <AlertTitle>Balanço fora de equilíbrio</AlertTitle>
        <AlertDescription>
          Diferença de <Moeda valor={Math.abs(diferenca)} /> entre Ativo e Passivo+PL.
          Reveja os lançamentos do período antes do fechamento.
        </AlertDescription>
      </div>
    </Alert>
  );
}

function Cabecalho({
  titulo,
  total,
  tom,
}: {
  titulo: string;
  total: number;
  tom: "ok" | "info";
}) {
  const cor = tom === "ok" ? "var(--color-lime)" : "var(--color-blue)";
  return (
    <div
      className="flex items-center justify-between gap-2 px-5 py-3 border-b"
      style={{ borderColor: "var(--color-line)" }}
    >
      <div className="flex items-center gap-2">
        <span className="size-2 rounded-full" style={{ background: cor }} />
        <span className="text-sm font-bold text-[var(--color-txt)]">
          {titulo}
        </span>
      </div>
      <Pill tom={tom}>
        <span className="mono">
          <Moeda valor={total} />
        </span>
      </Pill>
    </div>
  );
}

function LinhaItem({ linha }: { linha: LinhaBalanco }) {
  const isGrupo = linha.destaque === "grupo";
  const isSubgrupo = linha.destaque === "subgrupo";
  return (
    <li
      className={cn(
        "grid grid-cols-[1fr_auto] gap-3 px-5 py-2 items-center",
        isGrupo && "bg-[var(--color-card-2)] py-2.5"
      )}
    >
      <span
        className={cn(
          "text-sm",
          isGrupo
            ? "text-[var(--color-txt)] font-bold"
            : isSubgrupo
              ? "text-[var(--color-txt)] font-semibold pl-3"
              : "text-[var(--color-txt-2)] pl-6"
        )}
      >
        {linha.rotulo}
      </span>
      <span
        className={cn(
          "mono text-right",
          isGrupo
            ? "text-sm font-bold text-[var(--color-txt)]"
            : isSubgrupo
              ? "text-sm font-semibold text-[var(--color-txt)]"
              : "text-xs text-[var(--color-txt-2)]"
        )}
      >
        <Moeda valor={linha.valor} />
      </span>
    </li>
  );
}
