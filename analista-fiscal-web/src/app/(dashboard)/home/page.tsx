"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { CreditCard } from "lucide-react";
import { FiscalHealthScore } from "@/components/fiscal/fiscal-health-score";
import { ProximaObrigacaoCard } from "@/components/home/proxima-obrigacao-card";
import { AlertasCard } from "@/components/home/alertas-card";
import { CalendarioMesCard } from "@/components/home/calendario-mes-card";
import { QuickActions } from "@/components/home/quick-actions";
import { SimplesNacionalCard } from "@/components/home/simples-nacional-card";
import { UrgenciaCard } from "@/components/home/urgencia-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useCountUp } from "@/lib/motion/use-count-up";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import { classificarUrgencia } from "@/lib/urgencia";
import { OBRIGACOES } from "@/lib/traducao/obrigacoes";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const GraficoReceitaImposto = dynamic(
  () =>
    import("@/components/home/grafico-receita-imposto").then((m) => ({
      default: m.GraficoReceitaImposto,
    })),
  { ssr: false, loading: () => <Skeleton className="h-[280px] w-full" /> }
);

/**
 * dataAtualCurta — retorna "18 jun. 2026" sem usar biblioteca externa.
 * Usada no eyebrow da home para situar o usuário no tempo.
 */
function dataAtualCurta(): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date());
}

/**
 * HomePage v2 — "Arkan Claro"
 *
 * Responde 3 perguntas em ordem:
 *  (1) "Quanto pago agora?" → número-herói (valorDAS) + ação primária "Pagar guia"
 *  (2) "Estou bem?" → health score compacto + próxima obrigação
 *  (3) "Quanto este mês?" → simples/limites + alertas
 *  Abaixo da dobra: gráfico, calendário, atalhos
 *
 * Gates v2: sem saudação; 1 herói; 1 ação primária; ≤3 blocos acima da dobra;
 * mono em todo dado; verde só em saúde/ação; sem crop marks em painel comum.
 */
export default function HomePage() {
  const reduced = useReducedMotion();
  const { empresa } = useEmpresaAtual();
  const { data: apuracao, isLoading: loadingApuracao } = useApuracaoAtual();

  /* ── número-herói: valorDAS (imposto a pagar no mês) ── */
  const valorDAS = apuracao?.valorDAS ?? 0;
  const vencimento = apuracao?.vencimento ?? null;
  const urg = vencimento ? classificarUrgencia(vencimento) : null;

  /* count-up em centavos para evitar jitter no decimal */
  const dasCentavos = Math.round(valorDAS * 100);
  const heroRaw = useCountUp(dasCentavos, {
    id: "home:valorDAS",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

  /* ── motion ── */
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
      {/* ── Card de urgência — fixo quando há vencimento ≤3 dias ── */}
      <UrgenciaCard />

      {/* ═══════════════════════════════════════════════════════
          BLOCO 1 — Herói + ação primária
          Pergunta: "Quanto pago agora?"
          ═══════════════════════════════════════════════════════ */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4"
      >
        {/* eyebrow: situa o usuário no tempo sem saudação */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemVariants}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Início · <span style={{ fontVariantNumeric: "tabular-nums" }}>{dataAtualCurta()}</span>
            </motion.span>
            <motion.h1
              variants={itemVariants}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Visão geral
            </motion.h1>
          </div>

          {/* ── ação primária única: Pagar guia, verde 44px ── */}
          <motion.div variants={itemVariants} className="shrink-0 pt-5 md:pt-6">
            <Button asChild size="default" className="h-11 px-5 gap-2">
              <Link href="/fiscal/guias">
                <CreditCard className="size-4" aria-hidden />
                Pagar guia
              </Link>
            </Button>
          </motion.div>
        </div>

        {/* ── número-herói: valor do imposto mensal (DAS/guia) ── */}
        <motion.div variants={itemVariants} className="flex flex-col gap-1">
          {loadingApuracao ? (
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
                aria-label={`Guia mensal de impostos: ${heroFormatado}`}
              >
                {heroFormatado}
              </span>
              <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
                {OBRIGACOES.DAS.titulo.toLowerCase()}
                {vencimento ? (
                  <>
                    {" · vence em "}
                    <span
                      className="mono font-semibold text-[var(--color-ink)]"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {formatarDataBR(vencimento)}
                    </span>
                    {urg && urg.nivel !== "neutro" ? (
                      <span
                        className="ml-2"
                        style={{
                          color:
                            urg.nivel === "danger"
                              ? "var(--color-danger)"
                              : "var(--color-ochre)",
                        }}
                      >
                        · <strong>{urg.rotulo}</strong>
                      </span>
                    ) : null}
                  </>
                ) : null}
              </span>
              {/* empresa em contexto — ink-2, nunca ink-3 para dado load-bearing */}
              {empresa?.razaoSocial ? (
                <span
                  className="mono text-[11px] text-[var(--color-ink-2)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {empresa.razaoSocial}
                  {empresa.regime ? (
                    <abbr
                      title={empresa.regime}
                      className="ml-2 no-underline text-[var(--color-ink-2)]"
                    >
                      {empresa.regime === "SIMPLES_NACIONAL" ? "Simples" : empresa.regime}
                    </abbr>
                  ) : null}
                </span>
              ) : null}
            </>
          )}
        </motion.div>
      </motion.header>

      {/* ═══════════════════════════════════════════════════════
          BLOCO 2 — Saúde fiscal + próxima obrigação
          Pergunta: "Estou bem?"
          ═══════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* health score ocupa 2/3 da largura no lg */}
        <div className="lg:col-span-2">
          <FiscalHealthScore />
        </div>
        {/* próxima obrigação: contextualiza sem ser primária */}
        <ProximaObrigacaoCard />
      </div>

      {/* ═══════════════════════════════════════════════════════
          BLOCO 3 — Limites do Simples + Alertas
          Pergunta: "Quanto este mês / que situação estou?"
          ═══════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* simples nacional com RulerGauge — ocupa 2/3 */}
        <div className="lg:col-span-2">
          <SimplesNacionalCard />
        </div>
        <AlertasCard />
      </div>

      {/* ═══════════════════════════════════════════════════════
          ABAIXO DA DOBRA — Atalhos + gráfico + calendário
          ═══════════════════════════════════════════════════════ */}

      {/* atalhos rápidos — secundários na v2 */}
      <QuickActions />

      {/* gráfico receita × imposto + calendário fiscal */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GraficoReceitaImposto />
        <CalendarioMesCard />
      </div>
    </motion.div>
  );
}
