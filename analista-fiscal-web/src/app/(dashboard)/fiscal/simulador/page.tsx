"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { Calculator, Sparkles, TrendingDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/shared/pill";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { formatarMoeda, formatarMoedaCompacta } from "@/lib/format/moeda";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  simular,
  type AtividadeSimulada,
  type CenarioSimulado,
  type RegimeSimulado,
} from "@/lib/fiscal/simulador-regime";
import { cn } from "@/lib/utils";

const SimuladorBarChart = dynamic(
  () =>
    import("@/components/fiscal/simulador-bar-chart").then((m) => ({
      default: m.SimuladorBarChart,
    })),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> }
);

const ATIVIDADES: Array<{ id: AtividadeSimulada; label: string }> = [
  { id: "comercio", label: "Comércio (Anexo I)" },
  { id: "industria", label: "Indústria (Anexo II)" },
  { id: "servicos_anexo3", label: "Serviços — Anexo III" },
  { id: "servicos_anexo5", label: "Serviços intelectuais — Anexo V" },
];

const CORES_REGIME: Record<RegimeSimulado, string> = {
  SIMPLES: "var(--color-lime)",
  PRESUMIDO: "var(--color-blue)",
  REAL: "var(--color-amber)",
};

export default function FiscalSimuladorPage() {
  const { empresa } = useEmpresaAtual();
  const [faturamento, setFaturamento] = React.useState<number>(
    empresa?.faturamento12m ?? 850_000
  );
  const [atividade, setAtividade] = React.useState<AtividadeSimulada>(
    empresa?.anexoSimples === "I"
      ? "comercio"
      : empresa?.anexoSimples === "II"
        ? "industria"
        : empresa?.anexoSimples === "V"
          ? "servicos_anexo5"
          : "servicos_anexo3"
  );
  const [funcionarios, setFuncionarios] = React.useState<number>(3);

  const resultado = React.useMemo(
    () =>
      simular({
        faturamentoAnual: Math.max(0, faturamento),
        atividade,
        numeroFuncionarios: Math.max(0, funcionarios),
      }),
    [faturamento, atividade, funcionarios]
  );

  const dadosChart = resultado.cenarios.map((c) => ({
    rotulo: c.rotulo.split("·")[0]!.trim(),
    Imposto: c.impostoTotal,
    regime: c.regime,
  }));

  const economia =
    Math.max(...resultado.cenarios.map((c) => c.impostoTotal)) -
    Math.min(...resultado.cenarios.map((c) => c.impostoTotal));

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo fiscal
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Simulador de regime tributário
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Compare quanto sua empresa pagaria em cada regime — sem ter que
          consultar tabela.
        </p>
      </header>

      <FiscalSubnav />

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        <Card className="p-5 flex flex-col gap-4 self-start">
          <div className="flex items-center gap-2">
            <Calculator className="size-4 text-[var(--color-lime)]" />
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Parâmetros
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fat">Faturamento anual</Label>
            <Input
              id="fat"
              type="number"
              min={0}
              step={10000}
              value={faturamento}
              onChange={(e) => setFaturamento(Number(e.target.value))}
              className="mono"
            />
            <span className="text-[11px] text-[var(--color-txt-3)] mono">
              {formatarMoeda(faturamento)}
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Atividade</Label>
            <Select
              value={atividade}
              onValueChange={(v) => setAtividade(v as AtividadeSimulada)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ATIVIDADES.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="func">Número de funcionários</Label>
            <Input
              id="func"
              type="number"
              min={0}
              value={funcionarios}
              onChange={(e) => setFuncionarios(Number(e.target.value))}
              className="mono"
            />
            <span className="text-[11px] text-[var(--color-txt-3)]">
              CLT, com salário médio de R$ 4,5k.
            </span>
          </div>

          <div
            className="rounded-md border p-3 flex flex-col gap-1"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
              <Sparkles className="size-3 text-[var(--color-lime)]" />
              Economia possível
            </span>
            <span className="mono text-2xl font-extrabold text-[var(--color-lime)]">
              {formatarMoedaCompacta(economia)}/ano
            </span>
            <span className="text-[11px] text-[var(--color-txt-3)] leading-snug">
              Diferença entre o regime mais caro e o mais barato.
            </span>
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {resultado.cenarios.map((c) => (
              <CenarioCard
                key={c.regime}
                cenario={c}
                vencedor={resultado.vencedor === c.regime}
              />
            ))}
          </div>

          <Card className="p-5 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <TrendingDown className="size-4 text-[var(--color-blue)]" />
              <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
                Imposto anual estimado
              </span>
            </div>
            <div className="h-64 -ml-2">
              <SimuladorBarChart pontos={dadosChart} cores={CORES_REGIME} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function CenarioCard({
  cenario,
  vencedor,
}: {
  cenario: CenarioSimulado;
  vencedor: boolean;
}) {
  const tom =
    cenario.recomendacao === "vantajoso"
      ? "ok"
      : cenario.recomendacao === "neutro"
        ? "warn"
        : "error";
  const cor = CORES_REGIME[cenario.regime];
  return (
    <Card
      className={cn(
        "p-5 flex flex-col gap-3 relative overflow-hidden",
        vencedor && "ring-1 ring-[var(--color-lime)]/40"
      )}
      style={{
        background: vencedor ? "var(--color-lime-d)" : undefined,
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{ background: cor }}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
          {cenario.rotulo}
        </span>
        {vencedor ? <Pill tom="ok">Mais econômico</Pill> : <Pill tom={tom}>{cenario.recomendacao}</Pill>}
      </div>

      <div className="flex flex-col gap-0.5">
        <span className="mono text-3xl font-extrabold text-[var(--color-txt)] leading-none">
          {formatarMoedaCompacta(cenario.impostoTotal)}
        </span>
        <span className="text-xs text-[var(--color-txt-2)]">
          {(cenario.percentualSobreFaturamento * 100).toFixed(1).replace(".", ",")}% sobre o faturamento · ano
        </span>
      </div>

      <ul className="flex flex-col gap-1 border-t pt-3" style={{ borderColor: "var(--color-line)" }}>
        {cenario.detalhamento.map((d) => (
          <li
            key={d.tributo}
            className="flex items-center justify-between text-xs"
          >
            <span className="text-[var(--color-txt-2)]">{d.tributo}</span>
            <span className="mono text-[var(--color-txt)]">
              {formatarMoedaCompacta(d.valor)}
            </span>
          </li>
        ))}
      </ul>

      <p className="text-[11px] text-[var(--color-txt-3)] leading-snug border-t pt-3" style={{ borderColor: "var(--color-line)" }}>
        {cenario.observacao}
      </p>
    </Card>
  );
}
