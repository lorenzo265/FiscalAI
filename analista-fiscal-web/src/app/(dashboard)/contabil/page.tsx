"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, BookOpen, CheckCircle2, ChevronRight, EyeOff, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { ContabilSubnav } from "@/components/contabil/contabil-subnav";
import { useLancamentos } from "@/hooks/use-contabil";
import { montarBalancete, calcularResultadoExercicio } from "@/lib/contabil/motor";
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
import type { LinhaBalancete, NaturezaConta } from "@/lib/schemas/contabil";

const COR_NATUREZA: Record<NaturezaConta, string> = {
  ativo: "var(--color-green)",
  passivo: "var(--color-ochre)",
  patrimonio_liquido: "var(--color-ink-2)",
  receita: "var(--color-green)",
  despesa: "var(--color-ochre)",
  resultado: "var(--color-ink-2)",
};

export default function ContabilBalancetePage() {
  const { data, isLoading, isError, refetch } = useLancamentos();
  const [esconderZeradas, setEsconderZeradas] = React.useState(true);
  const reduced = useReducedMotion();

  const balancete = React.useMemo(
    () => (data ? montarBalancete(data) : null),
    [data]
  );

  /* ── número-herói: resultado do exercício (receita - despesa) ── */
  const resultado = React.useMemo(
    () => (data ? calcularResultadoExercicio(data) : { receita: 0, despesa: 0, resultado: 0 }),
    [data]
  );
  const resultadoCentavos = Math.round(Math.abs(resultado.resultado) * 100);
  const heroRaw = useCountUp(resultadoCentavos, {
    id: "contabil:resultado",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);
  const resultadoPositivo = resultado.resultado >= 0;

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
              Módulo contábil
            </motion.span>
            <motion.h1
              variants={itemV}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Balancete
            </motion.h1>
          </div>

          {/* Ação primária — verde 44px */}
          <motion.div variants={itemV} className="shrink-0 pt-5 md:pt-6">
            <Button asChild size="default" className="h-11 px-5 gap-2">
              <Link href="/contabil/lancamentos">
                <Plus className="size-4" aria-hidden />
                Novo lançamento
              </Link>
            </Button>
          </motion.div>
        </div>

        {/* número-herói: resultado do exercício */}
        <motion.div variants={itemV} className="flex flex-col gap-1">
          {isLoading ? (
            <>
              <Skeleton className="h-16 w-52" />
              <Skeleton className="h-4 w-40 mt-1" />
            </>
          ) : (
            <>
              <span
                className="mono leading-none whitespace-nowrap"
                style={{
                  fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                  fontWeight: 300,
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.02em",
                  color: resultadoPositivo
                    ? "var(--color-green)"
                    : "var(--color-danger)",
                }}
                aria-label={`Resultado do exercício: ${resultadoPositivo ? "lucro" : "prejuízo"} de ${heroFormatado}`}
              >
                {heroFormatado}
              </span>
              <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
                {resultadoPositivo ? "lucro" : "prejuízo"} do exercício{" "}
                {balancete?.totais.fechado ? (
                  <span className="text-[var(--color-green)] font-semibold">· balancete fechado</span>
                ) : null}
              </span>
            </>
          )}
        </motion.div>
      </motion.header>

      <ContabilSubnav />

      {isLoading ? (
        <LoadingState titulo="Calculando balancete..." />
      ) : isError || !balancete ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : (
        <>
          <BannerFechamento totais={balancete.totais} />

          {/* ── toggle zeradas ── */}
          <Framed marks={false} tone="rule" surface="card" className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <EyeOff className="size-4 text-[var(--color-ink-2)]" />
              <span className="text-sm text-[var(--color-ink)]">
                Esconder contas zeradas
              </span>
            </div>
            <Switch
              checked={esconderZeradas}
              onCheckedChange={setEsconderZeradas}
            />
          </Framed>

          {/* ── tabela ── */}
          <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
            <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)] flex items-center gap-2">
              <BookOpen className="size-4 text-[var(--color-ink-2)]" aria-hidden />
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
                Balancete de verificação
              </h2>
            </div>
            <div
              className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] gap-3 px-5 py-3 border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-2)] mono"
              style={{ borderColor: "var(--color-rule)" }}
            >
              <span>Conta</span>
              <span className="text-right">Saldo anterior</span>
              <span className="text-right">
                <abbr title="Lançamentos a débito">Débito</abbr>
              </span>
              <span className="text-right">
                <abbr title="Lançamentos a crédito">Crédito</abbr>
              </span>
              <span className="text-right">Saldo atual</span>
            </div>
            <div className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
              {balancete.raizes.map((raiz) => (
                <Linha
                  key={raiz.conta.codigo}
                  linha={raiz}
                  esconderZeradas={esconderZeradas}
                />
              ))}
            </div>
          </Framed>
        </>
      )}
    </motion.div>
  );
}

function BannerFechamento({
  totais,
}: {
  totais: { totalDebitos: number; totalCreditos: number; fechado: boolean };
}) {
  if (totais.fechado) {
    return (
      <Framed
        marks={false}
        tone="rule"
        surface="paper-2"
        className="flex items-center gap-3"
        style={{ borderColor: "var(--color-green)" }}
      >
        <CheckCircle2 className="size-5 text-[var(--color-green)] shrink-0" />
        <div className="flex flex-col flex-1 min-w-0">
          <span className="text-sm font-semibold text-[var(--color-ink)]">
            Balancete fechado — partidas dobradas conferindo
          </span>
          <span
            className="text-[12px] text-[var(--color-ink-2)] mono"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {"Σ"} débitos = {"Σ"} créditos = {formatarMoeda(totais.totalDebitos)}
          </span>
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
      <div className="flex flex-col flex-1 min-w-0">
        <span className="text-sm font-semibold text-[var(--color-ink)]">
          Balancete não fecha — diferença detectada
        </span>
        <span
          className="text-[12px] text-[var(--color-ink-2)] mono"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <abbr title="Débito" className="no-underline">D</abbr>{" "}
          {formatarMoeda(totais.totalDebitos)} ·{" "}
          <abbr title="Crédito" className="no-underline">C</abbr>{" "}
          {formatarMoeda(totais.totalCreditos)} · diferença{" "}
          {formatarMoeda(Math.abs(totais.totalDebitos - totais.totalCreditos))}
        </span>
      </div>
      <Pill tom="error" className="ml-auto shrink-0">
        atenção
      </Pill>
    </Framed>
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
          "grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr] gap-3 px-5 py-2.5 items-center hover:bg-[var(--color-paper-2)] transition-colors",
          ehSintetica && "bg-[var(--color-paper-2)]/60"
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
                "size-3.5 shrink-0 text-[var(--color-ink-2)] transition-transform",
                aberto && "rotate-90"
              )}
            />
          ) : (
            <span className="size-3.5 shrink-0" />
          )}
          <span
            className="size-1.5 rounded-[var(--radius-sm)] shrink-0"
            style={{ background: cor }}
          />
          <abbr
            title={`Código de conta: ${linha.conta.codigo}`}
            className="no-underline mono text-[11px] text-[var(--color-ink-2)] shrink-0 w-16"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {linha.conta.codigo}
          </abbr>
          {linha.conta.analitica ? (
            <Link
              href={`/contabil/razao/${encodeURIComponent(linha.conta.codigo)}`}
              className={cn(
                "text-sm truncate hover:text-[var(--color-green)] transition-colors text-left",
                ehSintetica
                  ? "font-bold text-[var(--color-ink)]"
                  : "text-[var(--color-ink)]"
              )}
            >
              {linha.conta.nome}
            </Link>
          ) : (
            <span
              className={cn(
                "text-sm truncate text-left",
                ehSintetica
                  ? "font-bold text-[var(--color-ink)]"
                  : "text-[var(--color-ink)]"
              )}
            >
              {linha.conta.nome}
            </span>
          )}
        </button>
        <span
          className="mono text-xs text-[var(--color-ink-2)] text-right"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarMoeda(linha.saldoAnterior)}
        </span>
        <span
          className={cn(
            "mono text-sm text-right",
            linha.debitos > 0
              ? "text-[var(--color-ink)]"
              : "text-[var(--color-ink-2)]"
          )}
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarMoeda(linha.debitos)}
        </span>
        <span
          className={cn(
            "mono text-sm text-right",
            linha.creditos > 0
              ? "text-[var(--color-ink)]"
              : "text-[var(--color-ink-2)]"
          )}
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarMoeda(linha.creditos)}
        </span>
        <span
          className="mono text-sm font-bold text-right"
          style={{
            color: linha.saldoAtual !== 0 ? cor : "var(--color-ink-2)",
            fontVariantNumeric: "tabular-nums",
          }}
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
