"use client";

import * as React from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  Plus,
  Search,
} from "lucide-react";
import { useQueryStates, parseAsString } from "nuqs";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Pill } from "@/components/shared/pill";
import { ContabilSubnav } from "@/components/contabil/contabil-subnav";
import { OrigemPill } from "@/components/contabil/origem-pill";
import { SeletorConta } from "@/components/contabil/seletor-conta";
import {
  useAdicionarLancamento,
  useLancamentos,
} from "@/hooks/use-contabil";
import { buscarConta, PLANO_CONTAS } from "@/lib/mocks/seeds/plano-contas";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import type {
  LancamentoContabil,
  OrigemLancamento,
} from "@/lib/schemas/contabil";

const ORIGENS: Array<{ id: string; label: string }> = [
  { id: "todos", label: "Todas as origens" },
  { id: "nf_saida", label: "NF saída" },
  { id: "nf_entrada", label: "NF entrada" },
  { id: "bancario", label: "Bancário" },
  { id: "folha", label: "Folha" },
  { id: "fiscal", label: "Fiscal" },
  { id: "manual", label: "Manual" },
];

export default function LivroDiarioPage() {
  const { data, isLoading, isError, refetch } = useLancamentos();
  const adicionar = useAdicionarLancamento();

  const [filtros, setFiltros] = useQueryStates(
    {
      q: parseAsString.withDefault(""),
      origem: parseAsString.withDefault("todos"),
      conta: parseAsString.withDefault("todas"),
      periodo: parseAsString.withDefault("180d"),
    },
    { history: "replace" }
  );

  const [aberto, setAberto] = React.useState(false);

  const filtrados = React.useMemo<LancamentoContabil[]>(() => {
    if (!data) return [];
    const corte = corteData(filtros.periodo);
    const q = filtros.q.trim().toLowerCase();
    return data.filter((l) => {
      if (corte && new Date(l.data).getTime() < corte) return false;
      if (filtros.origem !== "todos" && l.origem !== filtros.origem)
        return false;
      if (
        filtros.conta !== "todas" &&
        l.contaDebito !== filtros.conta &&
        l.contaCredito !== filtros.conta
      )
        return false;
      if (q && !l.historico.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [data, filtros]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Módulo contábil
          </span>
          <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Livro Diário
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
            Cada movimento da empresa virou partida dobrada. Sistema preenche
            automaticamente — você ajusta só o que é incomum.
          </p>
        </div>
        <Button onClick={() => setAberto(true)}>
          <Plus className="size-4" /> Novo lançamento manual
        </Button>
      </header>

      <ContabilSubnav />

      <Card className="p-4 flex flex-col md:flex-row md:items-center gap-3">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-txt-3)]" />
          <Input
            value={filtros.q}
            onChange={(e) => void setFiltros({ q: e.target.value })}
            placeholder="Buscar no histórico"
            className="pl-9"
          />
        </div>
        <Select
          value={filtros.origem}
          onValueChange={(v) => void setFiltros({ origem: v })}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ORIGENS.map((o) => (
              <SelectItem key={o.id} value={o.id}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filtros.conta}
          onValueChange={(v) => void setFiltros({ conta: v })}
        >
          <SelectTrigger className="w-full md:w-[260px]">
            <SelectValue placeholder="Conta" />
          </SelectTrigger>
          <SelectContent className="max-h-[320px]">
            <SelectItem value="todas">Todas as contas</SelectItem>
            {PLANO_CONTAS.filter((c) => c.analitica).map((c) => (
              <SelectItem key={c.codigo} value={c.codigo}>
                <span className="mono text-[11px] text-[var(--color-txt-3)] mr-2">
                  {c.codigo}
                </span>
                {c.nome}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filtros.periodo}
          onValueChange={(v) => void setFiltros({ periodo: v })}
        >
          <SelectTrigger className="w-full md:w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30d">30 dias</SelectItem>
            <SelectItem value="90d">90 dias</SelectItem>
            <SelectItem value="180d">6 meses</SelectItem>
            <SelectItem value="365d">12 meses</SelectItem>
            <SelectItem value="todos">Todos</SelectItem>
          </SelectContent>
        </Select>
      </Card>

      {isLoading ? (
        <LoadingState titulo="Carregando lançamentos..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : filtrados.length === 0 ? (
        <EmptyState
          titulo="Nenhum lançamento"
          descricao="Ajuste os filtros ou crie um lançamento manual."
        />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
            {[...filtrados]
              .sort((a, b) => b.data.localeCompare(a.data))
              .map((l) => (
                <LinhaLancamento key={l.id} lancamento={l} />
              ))}
          </ul>
        </Card>
      )}

      <NovoLancamentoDialog
        aberto={aberto}
        onAbertoChange={setAberto}
        onSalvar={async (l) => {
          await adicionar.mutateAsync(l);
          toast.success("Lançamento criado");
          setAberto(false);
        }}
        salvando={adicionar.isPending}
      />
    </div>
  );
}

function LinhaLancamento({ lancamento }: { lancamento: LancamentoContabil }) {
  const cD = buscarConta(lancamento.contaDebito);
  const cC = buscarConta(lancamento.contaCredito);
  const baixa = lancamento.confianca < 0.7;
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors">
      <div className="flex flex-col shrink-0 w-24">
        <span className="mono text-xs font-bold text-[var(--color-txt)]">
          {formatarDataBR(lancamento.data)}
        </span>
        <OrigemPill origem={lancamento.origem} />
      </div>

      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm text-[var(--color-txt)] truncate">
          {lancamento.historico}
        </span>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-txt-3)] mono flex-wrap">
          <span>
            <strong className="text-[var(--color-amber)]">D</strong>{" "}
            {lancamento.contaDebito} {cD?.nome ?? ""}
          </span>
          <ArrowLeftRight className="size-3" />
          <span>
            <strong className="text-[var(--color-lime)]">C</strong>{" "}
            {lancamento.contaCredito} {cC?.nome ?? ""}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {baixa ? (
          <span
            title={`Confiança ${Math.round(lancamento.confianca * 100)}%`}
            className="flex items-center gap-1 text-[11px] mono text-[var(--color-amber)]"
          >
            <AlertTriangle className="size-3.5" />
            {Math.round(lancamento.confianca * 100)}%
          </span>
        ) : null}
        <span className="mono text-base font-bold text-[var(--color-txt)]">
          {formatarMoeda(lancamento.valor)}
        </span>
      </div>
    </li>
  );
}

function NovoLancamentoDialog({
  aberto,
  onAbertoChange,
  onSalvar,
  salvando,
}: {
  aberto: boolean;
  onAbertoChange: (v: boolean) => void;
  onSalvar: (l: LancamentoContabil) => Promise<void>;
  salvando: boolean;
}) {
  const [data, setData] = React.useState(new Date().toISOString().slice(0, 10));
  const [debito, setDebito] = React.useState("");
  const [credito, setCredito] = React.useState("");
  const [valor, setValor] = React.useState("");
  const [historico, setHistorico] = React.useState("");

  const valorNumerico = Number(valor);
  const podeSalvar =
    debito && credito && debito !== credito && valorNumerico > 0 && historico.trim().length >= 5;

  return (
    <Dialog open={aberto} onOpenChange={onAbertoChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Novo lançamento manual</DialogTitle>
          <DialogDescription>
            Use somente quando o sistema não conseguir classificar
            automaticamente — eventos extraordinários, ajustes de fechamento, etc.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Data</Label>
            <Input
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
              className="mono"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Valor (R$)</Label>
            <Input
              type="number"
              min="0.01"
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="mono"
            />
          </div>
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>Conta débito</Label>
            <SeletorConta valor={debito} onSelecionar={setDebito} />
          </div>
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>Conta crédito</Label>
            <SeletorConta valor={credito} onSelecionar={setCredito} />
          </div>
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>Histórico</Label>
            <Input
              value={historico}
              onChange={(e) => setHistorico(e.target.value)}
              placeholder="Ex: Reembolso despesa de viagem ao cliente X"
            />
          </div>
        </div>

        {debito === credito && debito ? (
          <Pill tom="error" className="self-start">
            Débito e crédito não podem ser a mesma conta
          </Pill>
        ) : null}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onAbertoChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!podeSalvar || salvando}
            onClick={() =>
              onSalvar({
                id: `man-${Date.now()}`,
                data,
                contaDebito: debito,
                contaCredito: credito,
                valor: valorNumerico,
                historico: historico.trim(),
                origem: "manual" as OrigemLancamento,
                confianca: 1,
                criadoEm: new Date().toISOString(),
              })
            }
          >
            Salvar lançamento
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function corteData(periodo: string): number | null {
  const dias =
    periodo === "30d"
      ? 30
      : periodo === "90d"
        ? 90
        : periodo === "180d"
          ? 180
          : periodo === "365d"
            ? 365
            : null;
  if (dias == null) return null;
  return Date.now() - dias * 24 * 60 * 60 * 1000;
}
