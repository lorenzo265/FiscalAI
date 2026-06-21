"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useCountUp } from "@/lib/motion/use-count-up";
import { formatarMoeda } from "@/lib/format/moeda";
import { useDRE } from "@/hooks/use-relatorios";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";
import type { LinhaDre } from "@/lib/schemas/relatorios";

export default function DREPage() {
  const { data, isLoading, isError, refetch } = useDRE();
  const reduced = useReducedMotion();

  /* ── número-herói: resultado líquido (última linha de total) ── */
  const resultadoLiquido = React.useMemo(() => {
    if (!data) return 0;
    const ultima = [...data.linhas].reverse().find((l) => l.tipo === "total");
    return ultima?.valores[0] ?? 0;
  }, [data]);
  const heroRaw = useCountUp(Math.round(resultadoLiquido * 100), {
    id: "dre:resultado-liquido",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);
  const resultadoPositivo = resultadoLiquido >= 0;

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
      {/* ── cabeçalho + número-herói ── */}
      <motion.header
        className="flex flex-col gap-4"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <div>
          <motion.span
            variants={itemV}
            className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
          >
            Relatórios · DRE
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
          >
            Demonstrativo de Resultado
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Quanto entrou, quanto saiu, quanto sobrou. Comparamos o mês atual
            com o anterior e o mesmo mês do ano passado.
          </motion.p>
        </div>

        {/* número-herói: resultado líquido do período */}
        {!isLoading && data ? (
          <motion.div variants={itemV} className="flex flex-col gap-1">
            <span
              className="mono leading-none whitespace-nowrap"
              style={{
                fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                fontWeight: 300,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.02em",
                color: resultadoPositivo ? "var(--color-ink)" : "var(--color-danger)",
              }}
              aria-label={`Resultado líquido: ${heroFormatado}`}
            >
              {heroFormatado}
            </span>
            <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
              resultado líquido do período{" "}
              {resultadoPositivo ? (
                <Carimbo tom="green" sub="conferido">OK</Carimbo>
              ) : null}
            </span>
          </motion.div>
        ) : null}
      </motion.header>

      <RelatoriosSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando DRE..." />
      ) : isError || !data ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          {/* ── cards de margem ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {data.linhas
              .filter((l) => l.tipo === "margem")
              .map((linha) => (
                <CardMargem key={linha.chave} linha={linha} />
              ))}
          </div>

          {/* ── tabela DRE — marks=true é assinatura legítima (demonstrativo de print) ── */}
          <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Demonstrativo de resultado
              </h2>
            </div>

            {/* cabeçalho de colunas */}
            <div
              className="grid gap-3 px-5 py-3 border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono sticky top-0 bg-[var(--color-card)]"
              style={{
                gridTemplateColumns: "1.6fr repeat(3, 1fr)",
                borderColor: "var(--color-rule)",
              }}
            >
              <span>Conta</span>
              {data.periodos.map((p) => (
                <span key={p.rotulo} className="text-right">
                  {p.rotulo}
                </span>
              ))}
            </div>

            <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
              {data.linhas
                .filter((l) => l.tipo !== "margem")
                .map((linha) => (
                  <LinhaDreItem
                    key={linha.chave}
                    linha={linha}
                    ncols={data.periodos.length}
                  />
                ))}
            </ul>
          </Framed>
        </>
      )}
    </motion.div>
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
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-ink-3)] mono">
          {linha.rotulo}
        </span>
        <Pill tom={tom}>
          {tom === "ok" ? "saudável" : tom === "warn" ? "atenção" : "baixa"}
        </Pill>
      </div>
      <p
        className="mono text-2xl font-bold text-[var(--color-ink)]"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {atual.toFixed(1).replace(".", ",")}%
      </p>
      <span
        className="flex items-center gap-1 text-xs mono"
        style={{
          color: positivo ? "var(--color-green)" : "var(--color-danger)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        <Icon className="size-3" />
        {(delta >= 0 ? "+" : "") + delta.toFixed(1).replace(".", ",")}pp vs
        mês anterior
      </span>
    </Framed>
  );
}

function LinhaDreItem({
  linha,
  ncols,
}: {
  linha: LinhaDre;
  ncols: number;
}) {
  if (linha.tipo === "secao") {
    return (
      <li className="px-5 py-2.5 mt-2 first:mt-0">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)] mono">
          {linha.rotulo}
        </span>
      </li>
    );
  }

  const isTotal = linha.tipo === "total" || linha.tipo === "subtotal";
  return (
    <li
      className={cn(
        "grid gap-3 px-5 py-2.5 items-center",
        isTotal && "bg-[var(--color-paper-2)]",
        linha.tipo === "total" && "border-t-2"
      )}
      style={{
        gridTemplateColumns: `1.6fr repeat(${ncols}, 1fr)`,
        ...(linha.tipo === "total"
          ? { borderColor: "var(--color-rule-2)" }
          : undefined),
      }}
    >
      <span
        className={cn(
          "text-sm",
          linha.tipo === "deducao"
            ? "text-[var(--color-ink-2)] pl-3"
            : isTotal
              ? "text-[var(--color-ink)] font-bold"
              : "text-[var(--color-ink)]"
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
      ? "var(--color-danger)"
      : tom === "pos"
        ? "var(--color-green)"
        : "var(--color-ink)";
  return (
    <span
      className={cn(
        "mono text-right",
        enfase ? "text-base font-bold" : "text-sm"
      )}
      style={{ color: cor, fontVariantNumeric: "tabular-nums" }}
    >
      <Moeda valor={valor} />
    </span>
  );
}
