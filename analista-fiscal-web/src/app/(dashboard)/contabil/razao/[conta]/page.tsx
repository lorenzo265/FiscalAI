"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { OrigemPill } from "@/components/contabil/origem-pill";
import { useLancamentos } from "@/hooks/use-contabil";
import { montarRazao } from "@/lib/contabil/motor";
import { buscarConta } from "@/lib/mocks/seeds/plano-contas";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function RazaoContaPage() {
  const params = useParams<{ conta: string }>();
  const codigo = params?.conta ? decodeURIComponent(params.conta) : "";
  const conta = buscarConta(codigo);
  const { data, isLoading, isError, refetch } = useLancamentos();
  const reduced = useReducedMotion();

  const linhas = React.useMemo(() => {
    if (!data || !conta) return [];
    return montarRazao(conta, data);
  }, [data, conta]);

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  if (!conta) {
    return (
      <div className="flex flex-col gap-3 items-start">
        <p className="text-sm text-[var(--color-ink-2)]">
          Conta <span className="mono">{codigo}</span> não encontrada no plano de contas.
        </p>
        <Button asChild variant="outline">
          <Link href="/contabil">
            <ArrowLeft className="size-3.5" /> Voltar para o balancete
          </Link>
        </Button>
      </div>
    );
  }

  const totalDebitos = linhas.reduce((acc, l) => acc + l.debito, 0);
  const totalCreditos = linhas.reduce((acc, l) => acc + l.credito, 0);
  const saldoFinal = linhas.length > 0 ? linhas[linhas.length - 1]!.saldoApos : 0;

  return (
    <motion.div
      className="flex flex-col gap-6 print:gap-3"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      <style>{`
        @media print {
          body { background: white !important; }
          .no-print { display: none !important; }
          .print\\:bg-white { background: white !important; }
          .print\\:text-black { color: black !important; }
        }
      `}</style>

      {/* ── cabeçalho (screen only) ── */}
      <motion.div
        className="flex items-end justify-between gap-3 flex-wrap no-print"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <div className="flex flex-col gap-1">
          <motion.div variants={itemV}>
            <Link
              href="/contabil"
              className="text-[12px] text-[var(--color-ink-3)] hover:text-[var(--color-ink)] transition-colors flex items-center gap-1"
            >
              <ArrowLeft className="size-3" /> Voltar para o balancete
            </Link>
          </motion.div>
          <motion.span
            variants={itemV}
            className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold"
          >
            Razão analítico
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-serif text-[24px] md:text-[28px] tracking-tight text-[var(--color-ink)] leading-tight"
          >
            {conta.nome}
          </motion.h1>
          <motion.span
            variants={itemV}
            className="mono text-xs text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <abbr title="Código de conta" className="no-underline">Cód.</abbr>{" "}
            {conta.codigo} · {conta.natureza.replace("_", " ")}
          </motion.span>
        </div>
        <motion.div variants={itemV}>
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="size-3.5" /> Imprimir
          </Button>
        </motion.div>
      </motion.div>

      {/* ── cabeçalho para impressão ── */}
      <div className="hidden print:block mb-2">
        <h1 className="text-2xl font-bold text-black">
          Razão analítico — {conta.nome}
        </h1>
        <p className="text-sm text-black/70 mono">
          Código {conta.codigo} · Gerado em {formatarDataBR(new Date())}
        </p>
      </div>

      {isLoading ? (
        <LoadingState titulo="Carregando movimento..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : linhas.length === 0 ? (
        <EmptyState
          titulo="Sem movimento"
          descricao="Essa conta não tem lançamentos no período."
        />
      ) : (
        <Framed
          marks
          tone="ink"
          surface="card"
          padded={false}
          className="overflow-hidden print:bg-white print:border-black/30"
        >
          <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-3 no-print">
            <Fig n={1} titulo={`Razão — ${conta.nome}`} size="sm" />
          </div>
          <Ruler className="no-print" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono print:text-black"
                  style={{ borderColor: "var(--color-rule)" }}
                >
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Histórico</th>
                  <th className="px-4 py-3">Contraparte</th>
                  <th className="px-4 py-3 text-right">
                    <abbr title="Débito" className="no-underline">D</abbr>
                  </th>
                  <th className="px-4 py-3 text-right">
                    <abbr title="Crédito" className="no-underline">C</abbr>
                  </th>
                  <th className="px-4 py-3 text-right">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l) => (
                  <tr
                    key={l.lancamento.id}
                    className="border-b transition-colors hover:bg-[var(--color-paper-2)] print:hover:bg-white"
                    style={{ borderColor: "var(--color-rule)" }}
                  >
                    <td
                      className="px-4 py-3 align-top mono text-xs text-[var(--color-ink-2)] print:text-black"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {formatarDataBR(l.lancamento.data)}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <span className="text-[var(--color-ink)] print:text-black block">
                        {l.lancamento.historico}
                      </span>
                      <div className="mt-1 no-print">
                        <OrigemPill origem={l.lancamento.origem} />
                      </div>
                    </td>
                    <td
                      className="px-4 py-3 align-top mono text-[11px] text-[var(--color-ink-2)] print:text-black"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      <abbr
                        title={`Conta contraparte: ${l.contraparte}`}
                        className="no-underline"
                      >
                        {l.contraparte}
                      </abbr>
                    </td>
                    <td
                      className="px-4 py-3 align-top mono text-right"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      <span
                        className={
                          l.debito > 0
                            ? "text-[var(--color-ochre)] font-bold print:text-black"
                            : "text-[var(--color-ink-3)]"
                        }
                      >
                        {l.debito > 0 ? formatarMoeda(l.debito) : "—"}
                      </span>
                    </td>
                    <td
                      className="px-4 py-3 align-top mono text-right"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      <span
                        className={
                          l.credito > 0
                            ? "text-[var(--color-green)] font-bold print:text-black"
                            : "text-[var(--color-ink-3)]"
                        }
                      >
                        {l.credito > 0 ? formatarMoeda(l.credito) : "—"}
                      </span>
                    </td>
                    <td
                      className="px-4 py-3 align-top mono text-right font-bold text-[var(--color-ink)] print:text-black"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {formatarMoeda(l.saldoApos)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr
                  className="border-t bg-[var(--color-paper-2)] print:bg-white"
                  style={{ borderColor: "var(--color-rule-2)" }}
                >
                  <td
                    colSpan={3}
                    className="px-4 py-3 text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono print:text-black"
                  >
                    Totais do período
                  </td>
                  <td
                    className="px-4 py-3 mono text-right font-bold text-[var(--color-ochre)] print:text-black"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {formatarMoeda(totalDebitos)}
                  </td>
                  <td
                    className="px-4 py-3 mono text-right font-bold text-[var(--color-green)] print:text-black"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {formatarMoeda(totalCreditos)}
                  </td>
                  <td
                    className="px-4 py-3 mono text-right font-bold text-[var(--color-ink)] print:text-black"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {formatarMoeda(saldoFinal)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Framed>
      )}
    </motion.div>
  );
}
