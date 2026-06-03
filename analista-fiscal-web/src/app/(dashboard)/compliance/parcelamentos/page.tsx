"use client";

import { motion } from "framer-motion";
import { CheckCircle2, FileWarning } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { Carimbo } from "@/components/blueprint/carimbo";
import { ComplianceSubnav } from "@/components/compliance/compliance-subnav";
import { useParcelamentos } from "@/hooks/use-compliance";
import {
  ORGAO_LABEL,
  type Parcelamento,
} from "@/lib/schemas/compliance";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function ParcelamentosPage() {
  const { data, isLoading, isError, refetch } = useParcelamentos();
  const reduced = useReducedMotion();

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header variants={containerVariants} initial="hidden" animate="show">
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Compliance · Parcelamentos
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Parcelamentos fiscais
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          Refis, PERSE, PRT e outros programas de parcelamento. Acompanhamos
          cada parcela para que você não caia em rescisão.
        </motion.p>
      </motion.header>

      <ComplianceSubnav />

      {isLoading ? (
        <LoadingState titulo="Verificando parcelamentos..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-12">
          <EmptyState
            titulo="Nenhum débito parcelado"
            descricao="A empresa não está em nenhum programa de parcelamento — Refis, PERSE, PRT ou similar."
            icone={CheckCircle2}
          />
          {/* Carimbo — situação resolvida */}
          <Carimbo tom="green" sub="situação limpa">sem parcelamentos</Carimbo>
        </div>
      ) : (
        <Framed marks={false} tone="rule" surface="card" padded={false}>
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo="Parcelamentos ativos" size="sm" />
          </div>
          <Ruler />
          <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
            {data.map((p) => (
              <LinhaParcelamento key={p.id} parcelamento={p} />
            ))}
          </ul>
        </Framed>
      )}
    </motion.div>
  );
}

function LinhaParcelamento({ parcelamento }: { parcelamento: Parcelamento }) {
  const progresso =
    (parcelamento.parcelaAtual / parcelamento.totalParcelas) * 100;

  return (
    <li className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-4 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <FileWarning
            className="size-4 shrink-0"
            style={{ color: "var(--color-ochre)" }}
          />
          <span className="text-sm font-bold text-[var(--color-ink)] truncate">
            {parcelamento.assunto}
          </span>
        </div>
        <p className="text-[11px] mono text-[var(--color-ink-3)] mt-1">
          {ORGAO_LABEL[parcelamento.orgao]} · <abbr title="Número do processo">Nº</abbr> {parcelamento.numero}
        </p>
        {/* barra de progresso */}
        <div className="mt-2 flex items-center gap-2 text-xs">
          <div
            className="flex-1 h-1 rounded-[var(--radius-sm)] overflow-hidden"
            style={{ background: "var(--color-rule)" }}
            role="progressbar"
            aria-valuenow={parcelamento.parcelaAtual}
            aria-valuemax={parcelamento.totalParcelas}
            aria-label="Progresso do parcelamento"
          >
            <div
              className="h-full transition-all"
              style={{
                background: "var(--color-ochre)",
                width: `${progresso}%`,
              }}
            />
          </div>
          <span className="mono text-[var(--color-ink-2)] shrink-0"
                style={{ fontVariantNumeric: "tabular-nums" }}>
            {parcelamento.parcelaAtual}/{parcelamento.totalParcelas}
          </span>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1.5 shrink-0">
        <Pill tom={parcelamento.status === "ativo" ? "warn" : "ok"}>
          {parcelamento.status === "ativo" ? "ativo" : "encerrado"}
        </Pill>
        <span className="mono text-base font-bold text-[var(--color-ink)]"
              style={{ fontVariantNumeric: "tabular-nums" }}>
          <Moeda valor={parcelamento.saldoDevedor} />
        </span>
        <span className="text-[11px] text-[var(--color-ink-3)] mono"
              style={{ fontVariantNumeric: "tabular-nums" }}>
          Próxima {formatarDataBR(parcelamento.proximoVencimento)}
        </span>
      </div>
    </li>
  );
}
