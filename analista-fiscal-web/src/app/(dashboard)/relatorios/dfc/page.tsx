"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useDFC } from "@/hooks/use-relatorios";
import { formatarMesAnoBR } from "@/lib/format/data";
import { formatarMoeda } from "@/lib/format/moeda";
import { useCountUp } from "@/lib/motion/use-count-up";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";
import type { LinhaDfc } from "@/lib/schemas/relatorios";

export default function DFCPage() {
  const { data, isLoading, isError, refetch } = useDFC();
  const reduced = useReducedMotion();

  /* ── número-herói: saldo final de caixa ── */
  const saldoFinal = data?.saldoFinal ?? 0;
  const heroRaw = useCountUp(Math.round(saldoFinal * 100), {
    id: "dfc:saldo-final",
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
            Relatórios · DFC
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
          >
            Fluxo de Caixa
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Como o caixa se movimentou entre operações, investimentos e
            financiamento. Método indireto — partindo do lucro líquido.
          </motion.p>
        </div>

        {/* número-herói: saldo final de caixa */}
        {!isLoading && data ? (
          <motion.div variants={itemV} className="flex flex-col gap-1">
            <span
              className="mono leading-none whitespace-nowrap"
              style={{
                fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                fontWeight: 300,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.02em",
                color: saldoFinal >= 0 ? "var(--color-ink)" : "var(--color-danger)",
              }}
              aria-label={`Saldo final de caixa: ${heroFormatado}`}
            >
              {heroFormatado}
            </span>
            <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
              saldo final de caixa em{" "}
              <span className="text-[var(--color-ink)]">
                {formatarMesAnoBR(`${data.competencia}-01`)}
              </span>
            </span>
          </motion.div>
        ) : null}
      </motion.header>

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

          {/* marks=true é assinatura legítima (demonstrativo de print) */}
          <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Demonstração do fluxo de caixa
              </h2>
            </div>
            <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
              {data.linhas.map((linha) => (
                <LinhaDfcItem key={linha.chave} linha={linha} />
              ))}
            </ul>
          </Framed>
        </>
      )}
    </motion.div>
  );
}

function LinhaDfcItem({ linha }: { linha: LinhaDfc }) {
  if (linha.tipo === "secao") {
    return (
      <li className="px-5 py-3 bg-[var(--color-paper-2)]">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)] mono">
          {linha.rotulo}
        </span>
      </li>
    );
  }

  const isTotal = linha.tipo === "total";
  const isSub = linha.tipo === "subtotal";
  const cor =
    linha.valor < 0
      ? "var(--color-danger)"
      : isTotal
        ? "var(--color-green)"
        : "var(--color-ink)";

  return (
    <li
      className={cn(
        "grid grid-cols-[1fr_auto] gap-3 px-5 py-2.5 items-center",
        isSub && "bg-[var(--color-paper-2)]",
        isTotal && "border-t-2"
      )}
      style={isTotal ? { borderColor: "var(--color-rule-2)" } : undefined}
    >
      <span
        className={cn(
          "text-sm",
          isTotal
            ? "text-[var(--color-ink)] font-bold"
            : isSub
              ? "text-[var(--color-ink)] font-semibold"
              : "text-[var(--color-ink-2)] pl-3"
        )}
      >
        {linha.rotulo}
      </span>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "mono text-right",
            isTotal
              ? "text-base font-bold"
              : isSub
                ? "text-sm font-semibold"
                : "text-sm"
          )}
          style={{ color: cor, fontVariantNumeric: "tabular-nums" }}
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
