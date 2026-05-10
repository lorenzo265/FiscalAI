"use client";

import * as React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useDRE } from "@/hooks/use-relatorios";
import { cn } from "@/lib/utils";
import type { LinhaDre } from "@/lib/schemas/relatorios";

export default function DREPage() {
  const { data, isLoading, isError, refetch } = useDRE();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Relatórios · DRE
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Demonstrativo de Resultado
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Quanto entrou, quanto saiu, quanto sobrou. Comparamos o mês atual com o
          anterior e com o mesmo mês do ano passado pra você ver tendência.
        </p>
      </header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando DRE..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {data.linhas
              .filter((l) => l.tipo === "margem")
              .map((linha) => (
                <CardMargem key={linha.chave} linha={linha} />
              ))}
          </div>

          <Card className="overflow-hidden">
            <div
              className="grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-3 px-5 py-3 border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono sticky top-0 bg-[var(--color-card)]"
              style={{ borderColor: "var(--color-line)" }}
            >
              <span>Conta</span>
              {data.periodos.map((p) => (
                <span key={p.rotulo} className="text-right">
                  {p.rotulo}
                </span>
              ))}
            </div>

            <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
              {data.linhas
                .filter((l) => l.tipo !== "margem")
                .map((linha) => (
                  <LinhaDreItem key={linha.chave} linha={linha} />
                ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

function CardMargem({ linha }: { linha: LinhaDre }) {
  const atual = linha.valores[0] ?? 0;
  const anterior = linha.valores[1] ?? 0;
  const delta = atual - anterior;
  const positivo = delta >= 0;
  const tom: "ok" | "warn" | "error" =
    atual >= 15 ? "ok" : atual >= 5 ? "warn" : "error";
  const Icon = positivo ? TrendingUp : TrendingDown;

  return (
    <Card className="p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
          {linha.rotulo}
        </span>
        <Pill tom={tom}>{tom === "ok" ? "saudável" : tom === "warn" ? "atenção" : "baixa"}</Pill>
      </div>
      <p className="mono text-2xl font-bold text-[var(--color-txt)]">
        {atual.toFixed(1).replace(".", ",")}%
      </p>
      <span
        className="flex items-center gap-1 text-xs mono"
        style={{
          color: positivo ? "var(--color-lime)" : "var(--color-red)",
        }}
      >
        <Icon className="size-3" />
        {(delta >= 0 ? "+" : "") + delta.toFixed(1).replace(".", ",")}pp vs mês anterior
      </span>
    </Card>
  );
}

function LinhaDreItem({ linha }: { linha: LinhaDre }) {
  if (linha.tipo === "secao") {
    return (
      <li className="px-5 py-2.5 mt-2 first:mt-0">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          {linha.rotulo}
        </span>
      </li>
    );
  }

  const isTotal = linha.tipo === "total" || linha.tipo === "subtotal";
  return (
    <li
      className={cn(
        "grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-3 px-5 py-2.5 items-center",
        isTotal && "bg-[var(--color-card-2)]",
        linha.tipo === "total" && "border-t-2"
      )}
      style={
        linha.tipo === "total"
          ? { borderColor: "var(--color-line-2)" }
          : undefined
      }
    >
      <span
        className={cn(
          "text-sm",
          linha.tipo === "deducao"
            ? "text-[var(--color-txt-2)] pl-3"
            : isTotal
              ? "text-[var(--color-txt)] font-bold"
              : "text-[var(--color-txt)]"
        )}
      >
        {linha.rotulo}
      </span>
      {linha.valores.map((v, i) => (
        <ValorCelula
          key={i}
          valor={v}
          enfase={isTotal}
          tom={linha.tipo === "deducao" ? "neg" : isTotal ? "pos" : "neutro"}
        />
      ))}
    </li>
  );
}

function ValorCelula({
  valor,
  enfase,
  tom,
}: {
  valor: number;
  enfase: boolean;
  tom: "pos" | "neg" | "neutro";
}) {
  const cor =
    tom === "neg" || valor < 0
      ? "var(--color-red)"
      : tom === "pos"
        ? "var(--color-lime)"
        : "var(--color-txt)";
  return (
    <span
      className={cn(
        "mono text-right",
        enfase ? "text-base font-bold" : "text-sm"
      )}
      style={{ color: cor }}
    >
      <Moeda valor={valor} />
    </span>
  );
}
