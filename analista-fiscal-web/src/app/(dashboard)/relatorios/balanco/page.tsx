"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { Carimbo } from "@/components/blueprint/carimbo";
import { RelatoriosSubnav } from "@/components/relatorios/relatorios-subnav";
import { useBalanco } from "@/hooks/use-relatorios";
import { formatarMesAnoBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";
import type { LinhaBalanco } from "@/lib/schemas/relatorios";

export default function BalancoPage() {
  const { data, isLoading, isError, refetch } = useBalanco();
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
          Relatórios · Balanço Patrimonial
        </motion.span>
        <motion.h1
          variants={itemV}
          className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Balanço Patrimonial
        </motion.h1>
        <motion.p
          variants={itemV}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Tudo que a empresa tem (Ativo) deve ser igual ao que deve mais o
          capital próprio (Passivo + PL). Os dois lados lado a lado.
        </motion.p>
      </motion.header>

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
            {/* ── Ativo ── */}
            <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
              <CabecalhoLado titulo="Ativo" total={data.totalAtivo} tom="ok" />
              <Ruler />
              <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
                {data.ativo.map((l) => (
                  <LinhaItem key={l.codigo} linha={l} />
                ))}
              </ul>
            </Framed>

            {/* ── Passivo + PL ── */}
            <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
              <CabecalhoLado
                titulo="Passivo + Patrimônio Líquido"
                total={data.totalPassivo + data.totalPl}
                tom="info"
              />
              <Ruler />
              <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
                {data.passivoEPl.map((l) => (
                  <LinhaItem key={l.codigo} linha={l} />
                ))}
                <li
                  className="grid grid-cols-[1fr_auto] gap-3 px-5 py-3 bg-[var(--color-paper-2)] border-t-2"
                  style={{ borderColor: "var(--color-rule-2)" }}
                >
                  <span className="text-sm font-bold text-[var(--color-ink)]">
                    Total Passivo + PL
                  </span>
                  <span
                    className="mono text-sm font-bold text-[var(--color-ink)] text-right"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    <Moeda valor={data.totalPassivo + data.totalPl} />
                  </span>
                </li>
              </ul>
            </Framed>
          </div>
        </>
      )}
    </motion.div>
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
      <Framed
        marks={false}
        tone="rule"
        surface="paper-2"
        className="flex items-center gap-3"
        style={{ borderColor: "var(--color-green)" }}
      >
        <CheckCircle2 className="size-5 text-[var(--color-green)] shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[var(--color-ink)]">
            Balanço fechado em{" "}
            {formatarMesAnoBR(`${competencia}-01`)}
          </p>
          <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
            Ativo = Passivo + Patrimônio Líquido. Os números batem.
          </p>
        </div>
        <Carimbo tom="green" sub="conferido">OK</Carimbo>
      </Framed>
    );
  }
  return (
    <Framed
      marks={false}
      tone="rule"
      surface="paper-2"
      className="flex items-center gap-3"
      style={{ borderColor: "var(--color-danger)" }}
    >
      <AlertTriangle className="size-5 text-[var(--color-danger)] shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--color-ink)]">
          Balanço fora de equilíbrio
        </p>
        <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
          Diferença de{" "}
          <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
            <Moeda valor={Math.abs(diferenca)} />
          </span>{" "}
          entre Ativo e Passivo+PL. Reveja os lançamentos antes do fechamento.
        </p>
      </div>
    </Framed>
  );
}

function CabecalhoLado({
  titulo,
  total,
  tom,
}: {
  titulo: string;
  total: number;
  tom: "ok" | "info";
}) {
  const cor =
    tom === "ok" ? "var(--color-green)" : "var(--color-ink-2)";
  return (
    <div className="flex items-center justify-between gap-2 px-5 py-4">
      <Fig n={tom === "ok" ? 1 : 2} titulo={titulo} size="sm" />
      <Pill tom={tom}>
        <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
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
        isGrupo && "bg-[var(--color-paper-2)] py-2.5"
      )}
    >
      <span
        className={cn(
          "text-sm",
          isGrupo
            ? "text-[var(--color-ink)] font-bold"
            : isSubgrupo
              ? "text-[var(--color-ink)] font-semibold pl-3"
              : "text-[var(--color-ink-2)] pl-6"
        )}
      >
        {linha.rotulo}
      </span>
      <span
        className={cn(
          "mono text-right",
          isGrupo
            ? "text-sm font-bold text-[var(--color-ink)]"
            : isSubgrupo
              ? "text-sm font-semibold text-[var(--color-ink)]"
              : "text-xs text-[var(--color-ink-3)]"
        )}
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <Moeda valor={linha.valor} />
      </span>
    </li>
  );
}
