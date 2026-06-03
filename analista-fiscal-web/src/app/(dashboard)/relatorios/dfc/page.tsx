"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useDFC } from "@/hooks/use-relatorios";
import { formatarMesAnoBR } from "@/lib/format/data";
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
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemV}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Relatórios · DFC
        </motion.span>
        <motion.h1
          variants={itemV}
          className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
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

          <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-2">
              <Fig n={1} titulo="Demonstração do fluxo de caixa" size="sm" />
            </div>
            <Ruler />
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
