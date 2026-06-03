"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowUp,
  ArrowRight,
  Info,
  CalendarRange,
} from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  formatarMoeda,
  formatarMoedaCompacta,
} from "@/lib/format/moeda";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

interface MarcoReforma {
  ano: number;
  titulo: string;
  descricao: string;
  destaque?: boolean;
}

const TIMELINE: MarcoReforma[] = [
  {
    ano: 2026,
    titulo: "Início do período de teste",
    descricao:
      "CBS começa em 0,9% e IBS em 0,1% — ainda compensáveis com PIS/Cofins.",
  },
  {
    ano: 2027,
    titulo: "PIS e Cofins extintos",
    descricao:
      "CBS sobe para alíquota cheia. Imposto Seletivo (IS) entra em vigor sobre itens nocivos.",
    destaque: true,
  },
  {
    ano: 2029,
    titulo: "Transição estadual começa",
    descricao:
      "Início da redução gradual de ICMS e ISS. IBS sobe na mesma proporção.",
  },
  {
    ano: 2032,
    titulo: "Último ano de ICMS/ISS",
    descricao:
      "Apuração paralela: você recolhe parte no antigo, parte no IBS.",
  },
  {
    ano: 2033,
    titulo: "Sistema novo 100% em vigor",
    descricao:
      "ICMS e ISS extintos. CBS + IBS substituem PIS, Cofins, IPI, ICMS e ISS.",
    destaque: true,
  },
];

interface ComparativoLinha {
  antes: string;
  depois: string;
  observacao: string;
}

const COMPARATIVO: ComparativoLinha[] = [
  {
    antes: "PIS + Cofins (federal)",
    depois: "CBS — Contribuição sobre Bens e Serviços",
    observacao: "Não cumulativo, com créditos amplos.",
  },
  {
    antes: "ICMS + ISS (estadual + municipal)",
    depois: "IBS — Imposto sobre Bens e Serviços",
    observacao:
      "Cobrado no destino, não na origem. Fim da guerra fiscal entre estados.",
  },
  {
    antes: "IPI",
    depois: "Imposto Seletivo (IS)",
    observacao:
      "Apenas sobre bens prejudiciais à saúde ou ambiente (cigarro, bebida, etc).",
  },
  {
    antes: "Múltiplas obrigações acessórias",
    depois: "Nota fiscal única + split payment",
    observacao:
      "Sistema fica responsável por separar o imposto na hora do pagamento.",
  },
];

export default function FiscalReformaTributariaPage() {
  const { empresa } = useEmpresaAtual();
  const reduced = useReducedMotion();
  const fat = empresa?.faturamento12m ?? 850_000;

  const impostoAtualAprox = fat * 0.082;
  const impostoNovoAprox = fat * 0.094;
  const diferenca = impostoNovoAprox - impostoAtualAprox;
  const tendencia: "sobe" | "desce" | "neutro" =
    Math.abs(diferenca) < impostoAtualAprox * 0.02
      ? "neutro"
      : diferenca > 0
        ? "sobe"
        : "desce";

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
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Fiscal
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Reforma tributária 2026–2033
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          A maior mudança fiscal em 60 anos. Acompanhamos o calendário pra você
          não ser pego de surpresa.
        </motion.p>
      </motion.header>

      <FiscalSubnav />

      {/* ── destaque informativo ── */}
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col md:flex-row gap-5 items-start md:items-center">
        <div
          className="size-12 rounded-[var(--radius-md)] grid place-items-center shrink-0 border"
          style={{
            background: "var(--color-paper-2)",
            borderColor: "var(--color-rule-2)",
          }}
        >
          <CalendarRange className="size-5 text-[var(--color-ink-2)]" aria-hidden />
        </div>
        <div className="flex flex-col gap-1 flex-1">
          <Pill tom="info">Em vigor a partir de 2026</Pill>
          <h2 className="font-serif text-xl md:text-2xl text-[var(--color-ink)] tracking-tight leading-tight mt-1">
            A partir de 2026, o sistema tributário muda.
          </h2>
          <p className="text-sm text-[var(--color-ink-2)] max-w-2xl leading-relaxed">
            PIS, Cofins, IPI, ICMS e ISS deixam de existir. No lugar entram{" "}
            <abbr title="Contribuição sobre Bens e Serviços">CBS</abbr> (federal)
            e <abbr title="Imposto sobre Bens e Serviços">IBS</abbr> (estadual +
            municipal). Simulamos o impacto abaixo.
          </p>
        </div>
      </Framed>

      {/* ── linha do tempo ── */}
      <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
        <div className="flex items-center gap-2 px-5 pt-4 pb-2">
          <Fig n={1} titulo="Linha do tempo da transição" size="sm" />
        </div>
        <Ruler />
        <div className="px-5 py-4">
          <ol className="flex flex-col gap-0">
            {TIMELINE.map((m, i) => (
              <li key={m.ano} className="grid grid-cols-[80px_1fr] gap-4 relative">
                <div className="flex flex-col items-center pt-0.5">
                  <span
                    className={
                      "mono text-[12px] font-bold py-1 px-2 rounded-[var(--radius-md)] border " +
                      (m.destaque
                        ? "bg-[var(--color-green-wash)] text-[var(--color-green-deep)] border-[var(--color-green)]"
                        : "bg-[var(--color-paper-2)] text-[var(--color-ink-2)] border-[var(--color-rule)]")
                    }
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {m.ano}
                  </span>
                  {i < TIMELINE.length - 1 ? (
                    <span
                      className="w-px flex-1 my-1"
                      style={{ background: "var(--color-rule-2)" }}
                      aria-hidden
                    />
                  ) : null}
                </div>
                <div className="pb-5 flex flex-col gap-1">
                  <span className="text-sm font-semibold text-[var(--color-ink)]">
                    {m.titulo}
                  </span>
                  <p className="text-[12px] text-[var(--color-ink-2)] leading-relaxed max-w-2xl">
                    {m.descricao}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </Framed>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ── impacto estimado ── */}
        <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <Fig n={2} titulo="Impacto estimado pra você" size="sm" />
            <Pill
              tom={
                tendencia === "sobe"
                  ? "warn"
                  : tendencia === "desce"
                    ? "ok"
                    : "neutral"
              }
            >
              {tendencia === "sobe"
                ? "tende a subir"
                : tendencia === "desce"
                  ? "tende a cair"
                  : "neutro"}
            </Pill>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <BlocoImpacto
              label="Cenário atual"
              valor={impostoAtualAprox}
              detalhe="PIS + Cofins + ICMS/ISS estimados."
            />
            <BlocoImpacto
              label="Cenário pós-reforma"
              valor={impostoNovoAprox}
              detalhe="CBS + IBS · alíquota cheia."
              destaque
            />
          </div>

          <div
            className="rounded-[var(--radius-md)] border p-3 flex items-center gap-3"
            style={{
              background: "var(--color-paper-2)",
              borderColor: "var(--color-rule-2)",
            }}
          >
            {tendencia === "sobe" ? (
              <ArrowUp className="size-4 text-[var(--color-ochre)]" aria-hidden />
            ) : tendencia === "desce" ? (
              <ArrowDown className="size-4 text-[var(--color-green)]" aria-hidden />
            ) : (
              <ArrowRight className="size-4 text-[var(--color-ink-2)]" aria-hidden />
            )}
            <div className="flex flex-col">
              <span className="text-[11px] uppercase mono tracking-[0.14em] font-bold text-[var(--color-ink-3)]">
                Diferença anual estimada
              </span>
              <span
                className="mono text-lg font-bold"
                style={{
                  color:
                    tendencia === "sobe"
                      ? "var(--color-ochre)"
                      : tendencia === "desce"
                        ? "var(--color-green)"
                        : "var(--color-ink)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {diferenca >= 0 ? "+" : "-"}
                {formatarMoedaCompacta(Math.abs(diferenca))}
              </span>
            </div>
          </div>

          <p className="flex items-start gap-2 text-[11px] text-[var(--color-ink-3)] leading-snug">
            <Info className="size-3.5 mt-0.5 shrink-0" aria-hidden />
            Estimativa simplificada baseada em alíquotas cheias e faturamento de{" "}
            <span
              className="mono text-[var(--color-ink-2)] mx-1"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatarMoeda(fat)}
            </span>
            . O valor final depende do split de receita por estado/atividade.
          </p>
        </Framed>

        {/* ── comparativo antes × depois ── */}
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-2">
            <Fig n={3} titulo="Antes × depois" size="sm" />
          </div>
          <Ruler />
          <div className="overflow-x-auto px-5 py-4">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono border-b"
                  style={{ borderColor: "var(--color-rule)" }}
                >
                  <th className="py-2 pr-3 font-bold">Hoje</th>
                  <th className="py-2 px-1 font-bold">Depois</th>
                </tr>
              </thead>
              <tbody>
                {COMPARATIVO.map((c, i) => (
                  <tr
                    key={i}
                    className="border-b last:border-b-0"
                    style={{ borderColor: "var(--color-rule)" }}
                  >
                    <td className="py-3 pr-3 align-top">
                      <span className="text-[var(--color-ink-2)] line-through decoration-[var(--color-ink-3)]">
                        {c.antes}
                      </span>
                    </td>
                    <td className="py-3 px-1 align-top">
                      <span className="text-[var(--color-ink)] font-medium block">
                        {c.depois}
                      </span>
                      <span className="text-[11px] text-[var(--color-ink-3)] leading-snug block mt-0.5">
                        {c.observacao}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Framed>
      </div>
    </motion.div>
  );
}

function BlocoImpacto({
  label,
  valor,
  detalhe,
  destaque,
}: {
  label: string;
  valor: number;
  detalhe: string;
  destaque?: boolean;
}) {
  return (
    <div
      className="rounded-[var(--radius-md)] border p-3 flex flex-col gap-1"
      style={{
        background: destaque ? "var(--color-paper-2)" : "transparent",
        borderColor: destaque ? "var(--color-rule-2)" : "var(--color-rule)",
      }}
    >
      <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
        {label}
      </span>
      <span
        className="mono text-2xl font-extrabold text-[var(--color-ink)] leading-none"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {formatarMoedaCompacta(valor)}
      </span>
      <span className="text-[11px] text-[var(--color-ink-3)] leading-snug">
        {detalhe}
      </span>
    </div>
  );
}
