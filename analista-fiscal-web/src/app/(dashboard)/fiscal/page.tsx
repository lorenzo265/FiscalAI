"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  ArrowRight,
  Download,
  Gauge,
  Receipt,
  TrendingUp,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { useFiscalHistorico } from "@/hooks/use-fiscal-historico";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";

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

  if (apuracao.isLoading) {
    return (
      <PageShell>
        <LoadingState titulo="Carregando apuração do mês..." />
      </PageShell>
    );
  }

  if (apuracao.isError || !apuracao.data) {
    return (
      <PageShell>
        <ErrorState onTentarNovamente={() => void apuracao.refetch()} />
      </PageShell>
    );
  }

  const data = apuracao.data;
  const fat12 = data.faturamento12m;
  const usoSub = Math.min(100, (fat12 / data.sublimiteEstadual) * 100);
  const usoTeto = Math.min(100, (fat12 / data.tetoSimples) * 100);

  return (
    <PageShell>
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        <Card className="p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Receipt className="size-4 text-[var(--color-lime)]" />
              <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
                Apuração de {nomeMesAno(data.periodo.mes, data.periodo.ano)}
              </span>
            </div>
            <Pill tom={data.status === "pago" ? "ok" : "info"}>
              {data.status === "pago" ? "pago" : "em aberto"}
            </Pill>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Bloco
              label="Faturamento do mês"
              valor={formatarMoeda(data.faturamentoMes)}
              sub={`Faixa ${data.faixa} · faturamento 12m ${formatarMoedaCompacta(data.faturamento12m)}`}
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
        </Card>

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

      <Card className="p-6 flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-blue)]" />
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Composição do DAS
          </span>
          <span className="text-[11px] text-[var(--color-txt-3)] ml-2">
            Quanto desses {formatarMoeda(data.valorDAS)} vai para cada tributo
          </span>
        </div>
        <ComposicaoDonut composicao={data.composicao} total={data.valorDAS} />
      </Card>

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

      <Card className="p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-4 text-[var(--color-lime)]" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Histórico · últimos 12 meses
            </span>
          </div>
          <span className="text-[11px] text-[var(--color-txt-3)]">
            Clique em uma barra pra abrir o detalhe
          </span>
        </div>

        <div className="h-64 -ml-2">
          {historico.isLoading ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <HistoricoBarChart
              pontos={historico.data ?? []}
              destaque={{ ano: data.periodo.ano, mes: data.periodo.mes }}
            />
          )}
        </div>

        <div className="border-t pt-3" style={{ borderColor: "var(--color-line)" }}>
          <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5">
            {(historico.data ?? []).slice(-8).reverse().map((m) => {
              const atual =
                m.ano === data.periodo.ano && m.mes === data.periodo.mes;
              return (
                <li
                  key={`${m.ano}-${m.mes}`}
                  className={
                    "rounded-md border p-2.5 flex items-center justify-between gap-2 transition-colors hover:bg-[var(--color-card-2)] " +
                    (atual ? "border-[rgba(163,255,107,0.32)]" : "border-[var(--color-line)]")
                  }
                  style={{ background: atual ? "var(--color-lime-d)" : "transparent" }}
                >
                  <div className="flex flex-col">
                    <span className="text-[10px] mono uppercase tracking-[0.14em] text-[var(--color-txt-3)] font-bold">
                      {m.rotulo}/{String(m.ano).slice(2)}
                    </span>
                    <span className="text-[10px] text-[var(--color-txt-3)]">
                      receita {formatarMoedaCompacta(m.receita)}
                    </span>
                  </div>
                  <span
                    className="mono text-sm font-bold"
                    style={{ color: atual ? "var(--color-lime)" : "var(--color-txt)" }}
                  >
                    {formatarMoedaCompacta(m.imposto)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </Card>
    </PageShell>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo fiscal
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Sua apuração do mês
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Tudo o que você precisa pagar e por quê — em uma tela só.
        </p>
      </header>
      <FiscalSubnav />
      {children}
    </div>
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
      className="rounded-md border p-3.5 flex flex-col gap-1"
      style={{
        background: destaque ? "var(--color-card-2)" : "transparent",
        borderColor: "var(--color-line-2)",
      }}
    >
      <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
        {label}
      </span>
      <span
        className="mono font-bold text-[var(--color-txt)] leading-tight"
        style={{ fontSize: destaque ? 24 : 20 }}
      >
        {valor}
      </span>
      {sub ? (
        <span className="text-[11px] text-[var(--color-txt-3)] leading-snug">
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
  return (
    <Card className="p-6 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-amber)]" />
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Fator R
          </span>
        </div>
        <Pill tom={atencao ? "warn" : "ok"}>
          {atencao ? "atenção" : `Anexo ${anexo} mantido`}
        </Pill>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="mono text-4xl font-extrabold text-[var(--color-txt)]">
          {pct}%
        </span>
        <span className="text-xs text-[var(--color-txt-2)]">
          folha ÷ receita 12m
        </span>
      </div>
      <Progress
        value={Math.min(100, (valor / 0.5) * 100)}
        tom={atencao ? "amber" : "lime"}
      />
      <p className="text-xs text-[var(--color-txt-2)] leading-relaxed">
        Acima de <strong className="text-[var(--color-txt)]">28%</strong>, sua
        atividade fica no Anexo III (alíquota cai pela metade). Sua folga atual:{" "}
        <strong className="text-[var(--color-txt)] mono">
          {(folga * 100).toFixed(1).replace(".", ",")} pp
        </strong>
        .
      </p>
    </Card>
  );
}

function SemFatorRCard() {
  return (
    <Card className="p-6 flex flex-col gap-3 justify-center">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
        Fator R
      </span>
      <p className="text-sm text-[var(--color-txt-2)] leading-relaxed">
        Não se aplica ao seu regime. O Fator R é um cálculo do Simples
        Nacional para atividades que oscilam entre Anexo III e V.
      </p>
    </Card>
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
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-[var(--color-txt)]">
          {titulo}
        </span>
        <Pill tom={pillTom}>{uso.toFixed(0)}%</Pill>
      </div>
      <Progress value={uso} tom={tom} />
      <div className="flex items-baseline justify-between text-xs text-[var(--color-txt-2)]">
        <span className="mono">
          {formatarMoeda(atual)}
        </span>
        <span className="text-[var(--color-txt-3)]">
          de <span className="mono">{formatarMoeda(limite)}</span>
        </span>
      </div>
      <p className="text-[11px] text-[var(--color-txt-3)] leading-snug">
        {descricao}
      </p>
    </Card>
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
