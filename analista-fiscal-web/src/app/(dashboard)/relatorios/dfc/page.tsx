"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useDFC } from "@/hooks/use-relatorios";
import { formatarMesAnoBR } from "@/lib/format/data";
import { cn } from "@/lib/utils";
import type { LinhaDfc } from "@/lib/schemas/relatorios";

export default function DFCPage() {
  const { data, isLoading, isError, refetch } = useDFC();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Relatórios · DFC
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Demonstração do Fluxo de Caixa
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Como o caixa se movimentou entre operações, investimentos e
          financiamento. Método indireto — partindo do lucro líquido.
        </p>
      </header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando DFC..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard
              label="Saldo inicial"
              valor={<Moeda valor={data.saldoInicial} />}
              sub={formatarMesAnoBR(`${data.competencia}-01`)}
            />
            <StatCard
              label="Variação líquida"
              valor={<Moeda valor={data.saldoFinal - data.saldoInicial} />}
              pill={{
                tom: data.saldoFinal >= data.saldoInicial ? "ok" : "warn",
                texto:
                  data.saldoFinal >= data.saldoInicial
                    ? "geração de caixa"
                    : "consumo de caixa",
              }}
            />
            <StatCard
              label="Saldo final"
              valor={<Moeda valor={data.saldoFinal} />}
              pill={{
                tom: data.saldoFinal > 0 ? "ok" : "error",
                texto: data.saldoFinal > 0 ? "saudável" : "negativo",
              }}
            />
          </div>

          <Card className="overflow-hidden">
            <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
              {data.linhas.map((linha) => (
                <LinhaDfcItem key={linha.chave} linha={linha} />
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

function LinhaDfcItem({ linha }: { linha: LinhaDfc }) {
  if (linha.tipo === "secao") {
    return (
      <li className="px-5 py-3 bg-[var(--color-card-2)]">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          {linha.rotulo}
        </span>
      </li>
    );
  }

  const isTotal = linha.tipo === "total";
  const isSub = linha.tipo === "subtotal";
  const cor =
    linha.valor < 0 ? "var(--color-red)" : isTotal ? "var(--color-lime)" : "var(--color-txt)";

  return (
    <li
      className={cn(
        "grid grid-cols-[1fr_auto] gap-3 px-5 py-2.5 items-center",
        isSub && "bg-[var(--color-card-2)]",
        isTotal && "border-t-2"
      )}
      style={isTotal ? { borderColor: "var(--color-line-2)" } : undefined}
    >
      <span
        className={cn(
          "text-sm",
          isTotal
            ? "text-[var(--color-txt)] font-bold"
            : isSub
              ? "text-[var(--color-txt)] font-semibold"
              : "text-[var(--color-txt-2)] pl-3"
        )}
      >
        {linha.rotulo}
      </span>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "mono text-right",
            isTotal ? "text-base font-bold" : isSub ? "text-sm font-semibold" : "text-sm"
          )}
          style={{ color: cor }}
        >
          <Moeda valor={linha.valor} />
        </span>
        {isTotal ? (
          <Pill tom={linha.valor >= 0 ? "ok" : "error"}>
            {linha.valor >= 0 ? "geração" : "consumo"}
          </Pill>
        ) : null}
      </div>
    </li>
  );
}
