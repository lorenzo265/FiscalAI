"use client";

import * as React from "react";
import { motion, type Variants } from "framer-motion";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  ArrowRight,
  Download,
  Gauge,
  Receipt,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { useFiscalHistorico } from "@/hooks/use-fiscal-historico";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { FATOR_R, ANEXOS } from "@/lib/traducao/obrigacoes";

const ComposicaoDonut = dynamic(
  () =>
    import("@/components/fiscal/composicao-donut").then((m) => ({
      default: m.ComposicaoDonut,
    })),
  { ssr: false, loading: () => <Skeleton className="h-[260px] w-full" /> }
);

const HistoricoBarChart = dynamic(
  () =>
    import("@/components/fiscal/historico-bar-chart").then((m) => ({
      default: m.HistoricoBarChart,
    })),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> }
);

export default function FiscalApuracaoPage() {
  const { empresa } = useEmpresaAtual();
  const apuracao = useApuracaoAtual();
  const historico = useFiscalHistorico(12);
  const reduced = useReducedMotion();

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  if (apuracao.isLoading) {
    return (
      <PageShell reduced={reduced} pageReveal={pageReveal} containerVariants={containerVariants} itemVariants={itemVariants}>
        <LoadingState titulo="Carregando apuração do mês..." />
      </PageShell>
    );
  }

  if (apuracao.isError || !apuracao.data) {
    return (
      <PageShell reduced={reduced} pageReveal={pageReveal} containerVariants={containerVariants} itemVariants={itemVariants}>
        <ErrorState onTentarNovamente={() => void apuracao.refetch()} />
      </PageShell>
    );
  }

  const data = apuracao.data;
  const fat12 = data.faturamento12m;
  const usoSub = Math.min(100, (fat12 / data.sublimiteEstadual) * 100);
  const usoTeto = Math.min(100, (fat12 / data.tetoSimples) * 100);

  return (
    <PageShell reduced={reduced} pageReveal={pageReveal} containerVariants={containerVariants} itemVariants={itemVariants}>
      {/* ── apuração principal ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-2">
            <div className="flex items-center gap-2">
              <Receipt className="size-4 text-[var(--color-green)]" aria-hidden />
              <Fig n={1} titulo={`Apuração de ${nomeMesAno(data.periodo.mes, data.periodo.ano)}`} size="sm" />
            </div>
            <Pill tom={data.status === "pago" ? "ok" : "info"}>
              {data.status === "pago" ? "pago" : "em aberto"}
            </Pill>
          </div>
          <Ruler />

          <div className="px-5 py-4 flex flex-col gap-5">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Bloco
                label="Faturamento do mês"
                valor={formatarMoeda(data.faturamentoMes)}
                sub={`Faixa ${data.faixa} · 12m ${formatarMoedaCompacta(data.faturamento12m)}`}
              />
              <Bloco
                label="Alíquota efetiva"
                valor={`${(data.aliquotaEfetiva * 100).toFixed(2).replace(".", ",")}%`}
                sub={`Nominal ${(data.aliquotaNominal * 100).toFixed(1).replace(".", ",")}%`}
                destaque
              />
              <Bloco
                label="Valor do DAS"
                valor={formatarMoeda(data.valorDAS)}
                sub={`Vence em ${formatarDataBR(data.vencimento)}`}
                destaque
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button asChild>
                <Link href="/fiscal/guias">
                  <Download className="size-3.5" />
                  Gerar guia DAS
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/fiscal/simulador">
                  Simular outro regime
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          </div>
        </Framed>

        {data.fatorR ? (
          <FatorRCard
            valor={data.fatorR.valor}
            anexo={data.fatorR.anexoAtual}
            atencao={data.fatorR.atencao}
          />
        ) : (
          <SemFatorRCard />
        )}
      </div>

      {/* ── composição do DAS ── */}
      <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
        <div className="flex items-center gap-2 px-5 pt-4 pb-2">
          <Gauge className="size-4 text-[var(--color-ink-2)]" aria-hidden />
          <Fig n={2} titulo="Composição do DAS" size="sm" />
          <span className="text-[11px] text-[var(--color-ink-3)] ml-2">
            Quanto desses {formatarMoeda(data.valorDAS)} vai para cada tributo
          </span>
        </div>
        <Ruler />
        <div className="px-5 py-4">
          <ComposicaoDonut composicao={data.composicao} total={data.valorDAS} />
        </div>
      </Framed>

      {/* ── limites do Simples ── */}
      {empresa?.regime === "SIMPLES_NACIONAL" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <LimiteCard
            titulo="Sublimite estadual"
            descricao="Acima desse limite o ICMS sai do Simples e vai pra apuração estadual."
            atual={fat12}
            limite={data.sublimiteEstadual}
            uso={usoSub}
          />
          <LimiteCard
            titulo="Teto do Simples"
            descricao="Acima de R$ 4,8M sua empresa é desenquadrada do regime."
            atual={fat12}
            limite={data.tetoSimples}
            uso={usoTeto}
          />
        </div>
      ) : null}

      {/* ── histórico ── */}
      <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
        <div className="flex items-center justify-between gap-2 px-5 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-[var(--color-green)]" aria-hidden />
            <Fig n={3} titulo="Histórico · últimos 12 meses" size="sm" />
          </div>
          <span className="text-[11px] text-[var(--color-ink-3)]">
            Barra destacada = mês atual
          </span>
        </div>
        <Ruler />

        <div className="px-5 pb-4">
          <div className="h-64 -ml-2 pt-2">
            {historico.isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <HistoricoBarChart
                pontos={historico.data ?? []}
                destaque={{ ano: data.periodo.ano, mes: data.periodo.mes }}
              />
            )}
          </div>
        </div>

        <Ruler />

        <div className="px-4 py-3">
          <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5">
            {(historico.data ?? []).slice(-8).reverse().map((m) => {
              const atual =
                m.ano === data.periodo.ano && m.mes === data.periodo.mes;
              return (
                <li
                  key={`${m.ano}-${m.mes}`}
                  className="rounded-[var(--radius-md)] border p-2.5 flex items-center justify-between gap-2 transition-colors hover:bg-[var(--color-paper-2)]"
                  style={{
                    background: atual ? "var(--color-green-wash)" : "transparent",
                    borderColor: atual ? "var(--color-green)" : "var(--color-rule)",
                  }}
                >
                  <div className="flex flex-col">
                    <span className="text-[10px] mono uppercase tracking-[0.14em] text-[var(--color-ink-3)] font-bold">
                      {m.rotulo}/{String(m.ano).slice(2)}
                    </span>
                    <span className="text-[10px] text-[var(--color-ink-3)]">
                      {formatarMoedaCompacta(m.receita)}
                    </span>
                  </div>
                  <span
                    className="mono text-sm font-bold"
                    style={{
                      color: atual ? "var(--color-green)" : "var(--color-ink)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {formatarMoedaCompacta(m.imposto)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </Framed>
    </PageShell>
  );
}

function PageShell({
  children,
  reduced,
  pageReveal,
  containerVariants,
  itemVariants,
}: {
  children: React.ReactNode;
  reduced: boolean;
  pageReveal: Variants;
  containerVariants: Variants;
  itemVariants: Variants;
}) {
  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
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
          Sua apuração do mês
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Tudo o que você precisa pagar e por quê — em uma tela só.
        </motion.p>
      </motion.header>
      <FiscalSubnav />
      {children}
    </motion.div>
  );
}

function Bloco({
  label,
  valor,
  sub,
  destaque,
}: {
  label: string;
  valor: string;
  sub?: string;
  destaque?: boolean;
}) {
  return (
    <div
      className="rounded-[var(--radius-md)] border p-3.5 flex flex-col gap-1"
      style={{
        background: destaque ? "var(--color-paper-2)" : "transparent",
        borderColor: destaque ? "var(--color-rule-2)" : "var(--color-rule)",
      }}
    >
      <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
        {label}
      </span>
      <span
        className="mono font-bold text-[var(--color-ink)] leading-tight"
        style={{ fontSize: destaque ? 24 : 20, fontVariantNumeric: "tabular-nums" }}
      >
        {valor}
      </span>
      {sub ? (
        <span className="text-[11px] text-[var(--color-ink-3)] leading-snug">
          {sub}
        </span>
      ) : null}
    </div>
  );
}

function FatorRCard({
  valor,
  anexo,
  atencao,
}: {
  valor: number;
  anexo: "III" | "V";
  atencao: boolean;
}) {
  const pct = (valor * 100).toFixed(1).replace(".", ",");
  const folga = Math.max(0, valor - 0.28);
  const anexoTraduzido = ANEXOS[anexo];
  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-ochre)]" aria-hidden />
          {/* Título em PT — termoTecnico em abbr secundário */}
          <span className="text-sm font-semibold text-[var(--color-ink)]">
            {FATOR_R.titulo}
          </span>
          <abbr
            title={FATOR_R.termoTecnico}
            className="mono text-[10px] text-[var(--color-ink-3)] no-underline"
          >
            {FATOR_R.termoTecnico}
          </abbr>
        </div>
        <Pill tom={atencao ? "warn" : "ok"}>
          {atencao
            ? "atenção"
            : <>{anexoTraduzido.titulo} <abbr title={anexoTraduzido.termoTecnico} className="no-underline">{anexoTraduzido.termoTecnico}</abbr> mantido</>
          }
        </Pill>
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="mono text-4xl font-extrabold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {pct}%
        </span>
        <span className="text-xs text-[var(--color-ink-2)]">
          folha ÷ receita 12m
        </span>
      </div>
      <Progress
        value={Math.min(100, (valor / 0.5) * 100)}
        tom={atencao ? "amber" : "lime"}
      />
      <p className="text-xs text-[var(--color-ink-2)] leading-relaxed">
        {FATOR_R.efeito}
        {" "}Sua folga atual:{" "}
        <strong className="text-[var(--color-ink)] mono" style={{ fontVariantNumeric: "tabular-nums" }}>
          {(folga * 100).toFixed(1).replace(".", ",")} pp
        </strong>
        .
      </p>
    </Framed>
  );
}

function SemFatorRCard() {
  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3 justify-center">
      <span className="text-sm font-semibold text-[var(--color-ink)]">
        {FATOR_R.titulo}{" "}
        <abbr
          title={FATOR_R.termoTecnico}
          className="mono text-[10px] font-normal text-[var(--color-ink-3)] no-underline"
        >
          {FATOR_R.termoTecnico}
        </abbr>
      </span>
      <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
        Não se aplica ao seu regime. {FATOR_R.descricaoCurta}
      </p>
    </Framed>
  );
}

function LimiteCard({
  titulo,
  descricao,
  atual,
  limite,
  uso,
}: {
  titulo: string;
  descricao: string;
  atual: number;
  limite: number;
  uso: number;
}) {
  const tom = uso < 70 ? "lime" : uso < 90 ? "amber" : "red";
  const pillTom = uso < 70 ? "ok" : uso < 90 ? "warn" : "error";
  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-[var(--color-ink)]">
          {titulo}
        </span>
        <Pill tom={pillTom}>{uso.toFixed(0)}%</Pill>
      </div>
      <Progress value={uso} tom={tom} />
      <div
        className="flex items-baseline justify-between text-xs text-[var(--color-ink-2)]"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <span className="mono">{formatarMoeda(atual)}</span>
        <span className="text-[var(--color-ink-3)]">
          de <span className="mono">{formatarMoeda(limite)}</span>
        </span>
      </div>
      <p className="text-[11px] text-[var(--color-ink-3)] leading-snug">
        {descricao}
      </p>
    </Framed>
  );
}

function nomeMesAno(mes: number, ano: number): string {
  const meses = [
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
  return `${meses[mes - 1] ?? "—"} de ${ano}`;
}
