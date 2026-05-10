"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, BookOpen, ChevronRight, EyeOff } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { ContabilSubnav } from "@/components/contabil/contabil-subnav";
import { useLancamentos } from "@/hooks/use-contabil";
import { montarBalancete } from "@/lib/contabil/motor";
import { formatarMoeda } from "@/lib/format/moeda";
import { cn } from "@/lib/utils";
import type { LinhaBalancete, NaturezaConta } from "@/lib/schemas/contabil";

const COR_NATUREZA: Record<NaturezaConta, string> = {
  ativo: "var(--color-lime)",
  passivo: "var(--color-amber)",
  patrimonio_liquido: "var(--color-blue)",
  receita: "var(--color-lime)",
  despesa: "var(--color-amber)",
  resultado: "var(--color-blue)",
};

export default function ContabilBalancetePage() {
  const { data, isLoading, isError, refetch } = useLancamentos();
  const [esconderZeradas, setEsconderZeradas] = React.useState(true);

  const balancete = React.useMemo(
    () => (data ? montarBalancete(data) : null),
    [data]
  );

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo contábil
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Balancete
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Saldo de cada conta consolidado a partir dos lançamentos do livro
          diário.
        </p>
      </header>

      <ContabilSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando balancete..." />
      ) : isError || !balancete ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <BannerFechamento totais={balancete.totais} />

          <Card className="p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <EyeOff className="size-4 text-[var(--color-txt-3)]" />
              <span className="text-sm text-[var(--color-txt)]">
                Esconder contas zeradas
              </span>
            </div>
            <Switch
              checked={esconderZeradas}
              onCheckedChange={setEsconderZeradas}
            />
          </Card>

          <Card className="overflow-hidden">
            <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] gap-3 px-5 py-3 border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono"
              style={{ borderColor: "var(--color-line)" }}
            >
              <span>Conta</span>
              <span className="text-right">Saldo anterior</span>
              <span className="text-right">Débitos</span>
              <span className="text-right">Créditos</span>
              <span className="text-right">Saldo atual</span>
            </div>
            <div className="divide-y" style={{ borderColor: "var(--color-line)" }}>
              {balancete.raizes.map((raiz) => (
                <Linha
                  key={raiz.conta.codigo}
                  linha={raiz}
                  esconderZeradas={esconderZeradas}
                />
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function BannerFechamento({
  totais,
}: {
  totais: { totalDebitos: number; totalCreditos: number; fechado: boolean };
}) {
  if (totais.fechado) {
    return (
      <Card
        className="p-4 flex items-center gap-3"
        style={{
          background: "var(--color-lime-d)",
          borderColor: "rgba(163,255,107,0.32)",
        }}
      >
        <BookOpen className="size-5 text-[var(--color-lime)]" />
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-[var(--color-txt)]">
            Balancete fechado
          </span>
          <span className="text-[12px] text-[var(--color-txt-2)] mono">
            ∑ débitos = ∑ créditos = {formatarMoeda(totais.totalDebitos)} ·
            partidas dobradas conferindo.
          </span>
        </div>
        <Pill tom="ok" className="ml-auto">
          OK
        </Pill>
      </Card>
    );
  }

  return (
    <Card
      className="p-4 flex items-center gap-3"
      style={{
        background: "var(--color-red-d)",
        borderColor: "rgba(255,85,102,0.32)",
      }}
    >
      <AlertTriangle className="size-5 text-[var(--color-red)]" />
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-[var(--color-txt)]">
          Balancete não fecha
        </span>
        <span className="text-[12px] text-[var(--color-txt-2)] mono">
          débitos {formatarMoeda(totais.totalDebitos)} · créditos{" "}
          {formatarMoeda(totais.totalCreditos)} · diferença{" "}
          {formatarMoeda(Math.abs(totais.totalDebitos - totais.totalCreditos))}
        </span>
      </div>
      <Pill tom="error" className="ml-auto">
        Atenção
      </Pill>
    </Card>
  );
}

function Linha({
  linha,
  esconderZeradas,
  nivel = 0,
}: {
  linha: LinhaBalancete;
  esconderZeradas: boolean;
  nivel?: number;
}) {
  const [aberto, setAberto] = React.useState(nivel < 1);
  const temFilhos = linha.filhos.length > 0;
  const zerada =
    linha.debitos === 0 && linha.creditos === 0 && linha.saldoAtual === 0;
  if (esconderZeradas && zerada && !temFilhos) return null;

  const filhosVisiveis = linha.filhos.filter(
    (f) =>
      !esconderZeradas ||
      f.debitos !== 0 ||
      f.creditos !== 0 ||
      f.saldoAtual !== 0 ||
      f.filhos.length > 0
  );
  if (esconderZeradas && temFilhos && filhosVisiveis.length === 0 && zerada)
    return null;

  const cor = COR_NATUREZA[linha.conta.natureza];
  const ehSintetica = !linha.conta.analitica;

  return (
    <>
      <div
        className={cn(
          "grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] gap-3 px-5 py-2.5 items-center hover:bg-[var(--color-card-2)] transition-colors",
          ehSintetica && "bg-[var(--color-card-2)]/40"
        )}
      >
        <button
          type="button"
          onClick={() => temFilhos && setAberto((v) => !v)}
          className="flex items-center gap-2 min-w-0"
          style={{ paddingLeft: nivel * 16 }}
          disabled={!temFilhos}
        >
          {temFilhos ? (
            <ChevronRight
              className={cn(
                "size-3.5 shrink-0 text-[var(--color-txt-3)] transition-transform",
                aberto && "rotate-90"
              )}
            />
          ) : (
            <span className="size-3.5 shrink-0" />
          )}
          <span
            className="size-1.5 rounded-full shrink-0"
            style={{ background: cor }}
          />
          <span className="mono text-[11px] text-[var(--color-txt-3)] shrink-0 w-16">
            {linha.conta.codigo}
          </span>
          {linha.conta.analitica ? (
            <Link
              href={`/contabil/razao/${encodeURIComponent(linha.conta.codigo)}`}
              className={cn(
                "text-sm truncate hover:text-[var(--color-lime)] transition-colors text-left",
                ehSintetica
                  ? "font-bold text-[var(--color-txt)]"
                  : "text-[var(--color-txt)]"
              )}
            >
              {linha.conta.nome}
            </Link>
          ) : (
            <span
              className={cn(
                "text-sm truncate text-left",
                ehSintetica
                  ? "font-bold text-[var(--color-txt)]"
                  : "text-[var(--color-txt)]"
              )}
            >
              {linha.conta.nome}
            </span>
          )}
        </button>
        <span className="mono text-xs text-[var(--color-txt-3)] text-right">
          {formatarMoeda(linha.saldoAnterior)}
        </span>
        <span
          className={cn(
            "mono text-sm text-right",
            linha.debitos > 0
              ? "text-[var(--color-txt)]"
              : "text-[var(--color-txt-3)]"
          )}
        >
          {formatarMoeda(linha.debitos)}
        </span>
        <span
          className={cn(
            "mono text-sm text-right",
            linha.creditos > 0
              ? "text-[var(--color-txt)]"
              : "text-[var(--color-txt-3)]"
          )}
        >
          {formatarMoeda(linha.creditos)}
        </span>
        <span
          className="mono text-sm font-bold text-right"
          style={{ color: linha.saldoAtual !== 0 ? cor : "var(--color-txt-3)" }}
        >
          {formatarMoeda(linha.saldoAtual)}
        </span>
      </div>
      {aberto && temFilhos
        ? filhosVisiveis.map((f) => (
            <Linha
              key={f.conta.codigo}
              linha={f}
              esconderZeradas={esconderZeradas}
              nivel={nivel + 1}
            />
          ))
        : null}
    </>
  );
}
