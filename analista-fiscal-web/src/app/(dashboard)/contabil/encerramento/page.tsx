"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowUp,
  CalendarCheck,
  CheckCircle2,
  Loader2,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { Carimbo } from "@/components/blueprint/carimbo";
import { ContabilSubnav } from "@/components/contabil/contabil-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useLancamentos } from "@/hooks/use-contabil";
import { calcularResultadoExercicio } from "@/lib/contabil/motor";
import { formatarMoeda } from "@/lib/format/moeda";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const NOMES_MES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

type Estado = "pronto" | "fechando" | "fechado";

export default function EncerramentoPage() {
  const { empresa } = useEmpresaAtual();
  const { data: lancamentos, isLoading } = useLancamentos();
  const reduced = useReducedMotion();
  const hoje = React.useMemo(() => new Date(), []);
  const mesRef = hoje.getMonth() === 0 ? 12 : hoje.getMonth();
  const anoRef = hoje.getMonth() === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();

  const lancamentosMes = React.useMemo(() => {
    if (!lancamentos) return [];
    return lancamentos.filter((l) => {
      const d = new Date(l.data);
      return d.getFullYear() === anoRef && d.getMonth() + 1 === mesRef;
    });
  }, [lancamentos, anoRef, mesRef]);

  const resultado = React.useMemo(
    () => calcularResultadoExercicio(lancamentosMes),
    [lancamentosMes]
  );

  const [estado, setEstado] = React.useState<Estado>("pronto");

  const fechar = async () => {
    setEstado("fechando");
    await new Promise((r) => setTimeout(r, 2_400));
    setEstado("fechado");
    toast.success("Mês encerrado", {
      description: `Resultado de ${NOMES_MES[mesRef - 1]}/${anoRef} apurado e distribuído.`,
    });
  };

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
          Módulo contábil
        </motion.span>
        <motion.h1
          variants={itemV}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Encerramento do exercício
        </motion.h1>
        <motion.p
          variants={itemV}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Apura o resultado do mês, transfere para Lucros Acumulados e
          consolida o balancete.
        </motion.p>
      </motion.header>

      <ContabilSubnav />

      {isLoading ? (
        <LoadingState titulo="Lendo movimentação do mês..." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
          {/* ── painel principal ── */}
          <Framed marks tone="ink" surface="card" padded={false} className="flex flex-col">
            <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <CalendarCheck className="size-4 text-[var(--color-ink-2)]" />
                <Fig n="01" titulo="Período de referência" size="sm" />
              </div>
              <Pill tom={estado === "fechado" ? "ok" : "info"}>
                {estado === "fechado" ? "encerrado" : "em aberto"}
              </Pill>
            </div>

            <Ruler />

            <div className="px-5 py-4 flex flex-col gap-4">
              <h2 className="font-serif text-2xl text-[var(--color-ink)] tracking-tight capitalize">
                {NOMES_MES[mesRef - 1]} de {anoRef}
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <BlocoResultado
                  label="Receitas"
                  valor={resultado.receita}
                  icon={ArrowUp}
                  cor="var(--color-green)"
                />
                <BlocoResultado
                  label="Despesas"
                  valor={resultado.despesa}
                  icon={ArrowDown}
                  cor="var(--color-ochre)"
                />
                <BlocoResultado
                  label="Resultado"
                  valor={resultado.resultado}
                  icon={Sparkles}
                  cor={
                    resultado.resultado >= 0
                      ? "var(--color-green)"
                      : "var(--color-danger)"
                  }
                  destaque
                />
              </div>

              {estado === "pronto" ? (
                <Button
                  size="lg"
                  className="self-start mt-2"
                  onClick={fechar}
                  disabled={lancamentosMes.length === 0}
                >
                  Fechar {NOMES_MES[mesRef - 1]}/{anoRef}
                </Button>
              ) : null}

              {estado === "fechando" ? (
                <div
                  className="rounded-[var(--radius-sm)] border p-4 flex items-center gap-3"
                  style={{
                    background: "var(--color-paper-2)",
                    borderColor: "var(--color-rule)",
                  }}
                >
                  <Loader2 className="size-5 animate-spin text-[var(--color-green)] shrink-0" />
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-[var(--color-ink)]">
                      Apurando resultado do exercício...
                    </span>
                    <span className="text-[12px] text-[var(--color-ink-3)]">
                      Transferindo saldos de receita e despesa para Lucros
                      Acumulados (3.2.1).
                    </span>
                  </div>
                </div>
              ) : null}

              {estado === "fechado" ? (
                <motion.div
                  initial={reduced ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-[var(--radius-sm)] border p-4 flex items-start gap-3"
                  style={{
                    background: "var(--color-paper-2)",
                    borderColor:
                      resultado.resultado >= 0
                        ? "var(--color-green)"
                        : "var(--color-danger)",
                  }}
                >
                  <CheckCircle2
                    className="size-5 mt-0.5 shrink-0"
                    style={{
                      color:
                        resultado.resultado >= 0
                          ? "var(--color-green)"
                          : "var(--color-danger)",
                    }}
                  />
                  <div className="flex flex-col gap-1 flex-1 min-w-0">
                    <span className="text-sm font-semibold text-[var(--color-ink)]">
                      {NOMES_MES[mesRef - 1]}/{anoRef} encerrado
                    </span>
                    <p className="text-[13px] text-[var(--color-ink-2)] leading-relaxed">
                      Resultado do exercício:{" "}
                      <strong
                        className="mono"
                        style={{
                          color:
                            resultado.resultado >= 0
                              ? "var(--color-green)"
                              : "var(--color-danger)",
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {resultado.resultado >= 0 ? "Lucro" : "Prejuízo"} de{" "}
                        <Moeda valor={Math.abs(resultado.resultado)} />
                      </strong>
                      .{" "}
                      {resultado.resultado >= 0
                        ? "Distribuído conforme contrato social — Lucros Acumulados (3.2.1)."
                        : "Mantido em Prejuízos Acumulados para compensação futura."}
                    </p>
                  </div>
                  {/* Signature de motion: carimbo no estado resolvido */}
                  <Carimbo
                    tom={resultado.resultado >= 0 ? "green" : "danger"}
                    sub={`${NOMES_MES[mesRef - 1]}/${anoRef}`}
                    className="shrink-0"
                  >
                    {resultado.resultado >= 0 ? "lucro" : "prejuízo"}
                  </Carimbo>
                </motion.div>
              ) : null}
            </div>
          </Framed>

          {/* ── painel lateral: fluxo ── */}
          <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3 self-start">
            <Fig n="02" titulo="O que acontece quando você fecha" size="sm" />
            <ol className="flex flex-col gap-3 text-[13px] text-[var(--color-ink-2)] leading-relaxed">
              <Passo
                n={1}
                titulo="Apuração do resultado"
                descricao="Sistema soma todas as contas de receita (grupo 4) e despesa (grupo 5) do período."
              />
              <Passo
                n={2}
                titulo="Transferência para o PL"
                descricao="O saldo vai para Lucros Acumulados (3.2.1), zerando receitas e despesas para o próximo exercício."
              />
              <Passo
                n={3}
                titulo="Consolidação"
                descricao="Balancete fica congelado — qualquer ajuste posterior exige reabertura."
              />
            </ol>

            <div
              className="rounded-[var(--radius-sm)] border p-3 mt-2 text-[11px] text-[var(--color-ink-3)] leading-snug"
              style={{
                background: "var(--color-paper-2)",
                borderColor: "var(--color-rule)",
              }}
            >
              {empresa?.razaoSocial ?? "Empresa"} ·{" "}
              <abbr title="Cadastro Nacional de Pessoa Jurídica" className="no-underline">CNPJ</abbr>{" "}
              <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
                {empresa?.cnpj ?? "—"}
              </span>{" "}
              · demonstração Arkan
            </div>
          </Framed>
        </div>
      )}
    </motion.div>
  );
}

function BlocoResultado({
  label,
  valor,
  icon: Icon,
  cor,
  destaque,
}: {
  label: string;
  valor: number;
  icon: typeof ArrowUp;
  cor: string;
  destaque?: boolean;
}) {
  return (
    <div
      className="rounded-[var(--radius-sm)] border p-3 flex flex-col gap-1.5"
      style={{
        background: destaque ? "var(--color-paper-2)" : "transparent",
        borderColor: destaque ? cor : "var(--color-rule)",
      }}
    >
      <div className="flex items-center gap-1.5">
        <Icon className="size-3.5" style={{ color: cor }} />
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
          {label}
        </span>
      </div>
      <span
        className="mono font-bold leading-none"
        style={{
          color: cor,
          fontSize: destaque ? 28 : 22,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}

function Passo({
  n,
  titulo,
  descricao,
}: {
  n: number;
  titulo: string;
  descricao: string;
}) {
  return (
    <li className="flex gap-3">
      <span
        className="size-6 rounded-[var(--radius-sm)] grid place-items-center mono text-[11px] font-bold shrink-0"
        style={{
          background: "var(--color-paper-2)",
          color: "var(--color-green)",
          border: "1px solid var(--color-rule)",
        }}
      >
        {n}
      </span>
      <div className="flex flex-col gap-0.5">
        <span className="text-[var(--color-ink)] font-semibold">{titulo}</span>
        <span className="text-[var(--color-ink-3)] leading-snug">
          {descricao}
        </span>
      </div>
    </li>
  );
}
