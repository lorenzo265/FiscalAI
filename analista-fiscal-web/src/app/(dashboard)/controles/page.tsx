"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Plus, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { useFluxoCaixa, useContasPagarReceber } from "@/hooks/use-controles";
import { useCountUp } from "@/lib/motion/use-count-up";
import { formatarDataBR } from "@/lib/format/data";
import { formatarMoeda } from "@/lib/format/moeda";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const GraficoFluxoCaixa = dynamic(
  () =>
    import("@/components/controles/grafico-fluxo-caixa").then((m) => ({
      default: m.GraficoFluxoCaixa,
    })),
  { ssr: false, loading: () => <Skeleton className="h-[280px] w-full" /> }
);

export default function ControlesPage() {
  const { data: fluxo, isLoading, isError, refetch } = useFluxoCaixa(90);
  const { data: contas } = useContasPagarReceber();
  const reduced = useReducedMotion();

  /* ── número-herói: saldo de hoje ("como está o caixa agora?") ── */
  const saldoHoje = fluxo?.saldoHoje ?? 0;
  const saldoCentavos = Math.round(saldoHoje * 100);
  const heroRaw = useCountUp(saldoCentavos, {
    id: "controles:saldoHoje",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── Bloco 1: cabeçalho + número-herói + ação primária ── */}
      <motion.header
        variants={containerV}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemV}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Controles · Fluxo de caixa
            </motion.span>
            <motion.h1
              variants={itemV}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Visão de caixa
            </motion.h1>
          </div>

          {/* Ação primária — verde 44px */}
          <motion.div variants={itemV} className="shrink-0 pt-5 md:pt-6">
            <Button asChild size="default" className="h-11 px-5 gap-2">
              <Link href="/controles/bancos/conectar">
                <Plus className="size-4" aria-hidden />
                Conectar banco
              </Link>
            </Button>
          </motion.div>
        </div>

        {/* número-herói: saldo de hoje */}
        <motion.div variants={itemV} className="flex flex-col gap-1">
          {isLoading ? (
            <>
              <Skeleton className="h-16 w-52" />
              <Skeleton className="h-4 w-40 mt-1" />
            </>
          ) : (
            <>
              <span
                className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
                style={{
                  fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                  fontWeight: 300,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.02em",
                }}
                aria-label={`Saldo hoje: ${heroFormatado}`}
              >
                {heroFormatado}
              </span>
              <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
                saldo de hoje{" "}
                {saldoHoje < 0 ? (
                  <span className="text-[var(--color-danger)] font-semibold">· atenção: negativo</span>
                ) : (
                  <span className="text-[var(--color-green)] font-semibold">· saudável</span>
                )}
              </span>
              {fluxo?.saldo90d !== undefined ? (
                <span
                  className="mono text-[11px] text-[var(--color-ink-2)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  projeção 90 dias: {formatarMoeda(fluxo.saldo90d)}
                </span>
              ) : null}
            </>
          )}
        </motion.div>
      </motion.header>

      <ControlesSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando projeção..." />
      ) : isError || !fluxo ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <SinalSaldoNegativo
            diaNegativo={fluxo.diaSaldoNegativo}
            saldo90={fluxo.saldo90d}
          />

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Hoje"
              valor={<Moeda valor={fluxo.saldoHoje} />}
              pill={{
                tom: fluxo.saldoHoje > 0 ? "ok" : "error",
                texto: fluxo.saldoHoje > 0 ? "saudável" : "negativo",
              }}
            />
            <StatCard
              label="Em 30 dias"
              valor={<Moeda valor={fluxo.saldo30d} />}
              tom={fluxo.saldo30d > 0 ? "ok" : "error"}
              sub={<DeltaSaldo base={fluxo.saldoHoje} novo={fluxo.saldo30d} />}
            />
            <StatCard
              label="Em 60 dias"
              valor={<Moeda valor={fluxo.saldo60d} />}
              sub={<DeltaSaldo base={fluxo.saldoHoje} novo={fluxo.saldo60d} />}
            />
            <StatCard
              label="Em 90 dias"
              valor={<Moeda valor={fluxo.saldo90d} />}
              sub={<DeltaSaldo base={fluxo.saldoHoje} novo={fluxo.saldo90d} />}
            />
          </div>

          {/* ── gráfico de fluxo ── */}
          <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)] flex items-center justify-between gap-2 flex-wrap">
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Saldo histórico (30d) + projeção (90d)
              </h2>
              <div className="flex items-center gap-3 text-[10px] text-[var(--color-ink-2)] mono">
                <Legenda cor="var(--color-green)" texto="Histórico" />
                <Legenda cor="var(--color-ink-2)" texto="Projeção" tracejado />
              </div>
            </div>
            <div className="px-4 py-3">
              <GraficoFluxoCaixa pontos={fluxo.pontos} />
            </div>
          </Framed>

          <ResumoPagarReceber contas={contas ?? []} />
        </>
      )}
    </motion.div>
  );
}

function SinalSaldoNegativo({
  diaNegativo,
  saldo90,
}: {
  diaNegativo: string | null;
  saldo90: number;
}) {
  if (!diaNegativo) {
    return (
      <Alert variant="ok" className="flex items-start gap-3">
        <TrendingUp className="size-4 mt-0.5" />
        <div className="flex-1">
          <AlertTitle>Caixa em dia pelos próximos 90 dias</AlertTitle>
          <AlertDescription>
            Saldo projetado em 90 dias: <Moeda valor={saldo90} />.
          </AlertDescription>
        </div>
      </Alert>
    );
  }
  return (
    <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <AlertTriangle className="size-4 mt-0.5 shrink-0" />
        <div>
          <AlertTitle>
            Caixa pode ficar negativo em {formatarDataBR(diaNegativo)}
          </AlertTitle>
          <AlertDescription>
            A projeção mostra um cruzamento abaixo de zero. Revise as contas a
            pagar próximas do vencimento ou antecipe recebíveis.
          </AlertDescription>
        </div>
      </div>
      <Button asChild className="shrink-0">
        <Link href="/controles/pagar?status=pendente">
          Revisar contas a pagar <ArrowRight className="size-4" />
        </Link>
      </Button>
    </Alert>
  );
}

function DeltaSaldo({ base, novo }: { base: number; novo: number }) {
  const delta = novo - base;
  const pos = delta >= 0;
  const Icon = pos ? TrendingUp : TrendingDown;
  const cor = pos ? "var(--color-green)" : "var(--color-danger)";
  return (
    <span
      className="flex items-center gap-1 mono"
      style={{ color: cor, fontVariantNumeric: "tabular-nums" }}
    >
      <Icon className="size-3" />
      <Moeda valor={delta} /> vs hoje
    </span>
  );
}

function Legenda({
  cor,
  texto,
  tracejado,
}: {
  cor: string;
  texto: string;
  tracejado?: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="block w-4 h-[2px]"
        style={{
          background: tracejado ? "transparent" : cor,
          borderTop: tracejado ? `2px dashed ${cor}` : undefined,
        }}
      />
      {texto}
    </span>
  );
}

function ResumoPagarReceber({
  contas,
}: {
  contas: import("@/lib/schemas/controles").ContaPagarReceber[];
}) {
  const pagar = contas.filter((c) => c.tipo === "pagar" && c.status !== "pago");
  const receber = contas.filter((c) => c.tipo === "receber" && c.status !== "pago");
  const totalPagar = pagar.reduce((acc, c) => acc + c.valor, 0);
  const totalReceber = receber.reduce((acc, c) => acc + c.valor, 0);
  const atrasadosPagar = pagar.filter((c) => c.status === "atrasado").length;
  const atrasadosReceber = receber.filter((c) => c.status === "atrasado").length;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-ink-2)]">
            Contas a pagar pendentes
          </span>
          {atrasadosPagar > 0 ? (
            <Pill tom="error">{atrasadosPagar} atrasada{atrasadosPagar > 1 ? "s" : ""}</Pill>
          ) : (
            <Pill tom="neutral">{pagar.length} aberta{pagar.length === 1 ? "" : "s"}</Pill>
          )}
        </div>
        <p
          className="mono text-2xl font-bold text-[var(--color-danger)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={totalPagar} />
        </p>
        <Button asChild variant="outline" className="self-start">
          <Link href="/controles/pagar">Abrir contas a pagar</Link>
        </Button>
      </Framed>
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-ink-2)]">
            Contas a receber pendentes
          </span>
          {atrasadosReceber > 0 ? (
            <Pill tom="warn">{atrasadosReceber} em atraso</Pill>
          ) : (
            <Pill tom="neutral">{receber.length} aberta{receber.length === 1 ? "" : "s"}</Pill>
          )}
        </div>
        <p
          className="mono text-2xl font-bold text-[var(--color-green)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={totalReceber} />
        </p>
        <Button asChild variant="outline" className="self-start">
          <Link href="/controles/receber">Abrir contas a receber</Link>
        </Button>
      </Framed>
    </div>
  );
}
