"use client";

import * as React from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  Plus,
  Search,
} from "lucide-react";
import { motion } from "framer-motion";
import { useQueryStates, parseAsString } from "nuqs";
import { toast } from "sonner";
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
import { Framed } from "@/components/blueprint/framed";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
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
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
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
  const reduced = useReducedMotion();

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

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  /* ── colunas DataTable ── */
  const colunas = React.useMemo<DataTableColumn<LancamentoContabil>[]>(
    () => [
      {
        id: "data",
        header: "Data",
        mono: true,
        primary: true,
        cell: (l) => (
          <div className="flex flex-col gap-1">
            <span
              className="mono text-xs font-bold text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatarDataBR(l.data)}
            </span>
            <OrigemPill origem={l.origem} />
          </div>
        ),
        width: "8rem",
      },
      {
        id: "historico",
        header: "Histórico",
        cell: (l) => {
          const cD = buscarConta(l.contaDebito);
          const cC = buscarConta(l.contaCredito);
          return (
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-sm text-[var(--color-ink)] truncate">
                {l.historico}
              </span>
              {/* D/C — cor+palavra, nunca só cor */}
              <div
                className="flex items-center gap-2 text-[11px] text-[var(--color-ink-2)] mono flex-wrap"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                <span>
                  <abbr title={`Débito: conta ${l.contaDebito}`} className="no-underline">
                    <span className="text-[var(--color-ochre)] font-bold">D</span>
                  </abbr>{" "}
                  <span className="text-[var(--color-ink-2)]">{l.contaDebito}</span>{" "}
                  {cD?.nome ?? ""}
                </span>
                <ArrowLeftRight className="size-3 shrink-0 text-[var(--color-ink-2)]" />
                <span>
                  <abbr title={`Crédito: conta ${l.contaCredito}`} className="no-underline">
                    <span className="text-[var(--color-green)] font-bold">C</span>
                  </abbr>{" "}
                  <span className="text-[var(--color-ink-2)]">{l.contaCredito}</span>{" "}
                  {cC?.nome ?? ""}
                </span>
              </div>
            </div>
          );
        },
      },
      {
        id: "valor",
        header: "Valor",
        mono: true,
        align: "right",
        cell: (l) => {
          const baixa = l.confianca < 0.7;
          return (
            <div className="flex items-center gap-2 justify-end">
              {baixa ? (
                <span
                  title={`Confiança da classificação: ${Math.round(l.confianca * 100)}%`}
                  className="flex items-center gap-1 text-[11px] mono text-[var(--color-ochre)]"
                >
                  <AlertTriangle className="size-3.5" />
                  {Math.round(l.confianca * 100)}%
                </span>
              ) : null}
              <span
                className="mono text-base font-bold text-[var(--color-ink)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarMoeda(l.valor)}
              </span>
            </div>
          );
        },
        width: "9rem",
      },
    ],
    []
  );

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        className="flex items-end justify-between gap-3 flex-wrap"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
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
            Livro Diário
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Cada movimento da empresa virou partida dobrada. O sistema preenche
            automaticamente — você ajusta só o que é incomum.
          </motion.p>
        </div>

        {/* Ação primária — verde 44px */}
        <motion.div variants={itemV}>
          <Button size="default" className="h-11 px-5 gap-2" onClick={() => setAberto(true)}>
            <Plus className="size-4" aria-hidden />
            Novo lançamento manual
          </Button>
        </motion.div>
      </motion.header>

      <ContabilSubnav />

      {/* ── filtros ── */}
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col md:flex-row md:items-center gap-3">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
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
                <abbr
                  title={`Código: ${c.codigo}`}
                  className="no-underline mono text-[11px] text-[var(--color-ink-2)] mr-2"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {c.codigo}
                </abbr>
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
      </Framed>

      {/* ── lista ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando lançamentos..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : filtrados.length === 0 ? (
        <EmptyState
          titulo="Nenhum lançamento"
          descricao="Ajuste os filtros ou crie um lançamento manual."
          acao={
            <Button onClick={() => setAberto(true)}>
              <Plus className="size-4" /> Novo lançamento manual
            </Button>
          }
        />
      ) : (
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Livro Diário
            </h2>
          </div>

          <DataTable<LancamentoContabil>
            data={[...filtrados].sort((a, b) => b.data.localeCompare(a.data))}
            columns={colunas}
            getRowKey={(l) => l.id}
            getRowLabel={(l) => `${formatarDataBR(l.data)} — ${l.historico}`}
            caption="Livro Diário — lançamentos contábeis"
          />

          <div className="px-5 py-2.5 border-t border-[var(--color-rule)]">
            <span
              className="text-xs text-[var(--color-ink-2)] mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {filtrados.length} lançamento(s)
            </span>
          </div>
        </Framed>
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
    </motion.div>
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
              style={{ fontVariantNumeric: "tabular-nums" }}
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
              style={{ fontVariantNumeric: "tabular-nums" }}
            />
          </div>
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>
              <span className="text-[var(--color-ochre)] font-bold mr-1">D</span>
              Conta débito
            </Label>
            <SeletorConta valor={debito} onSelecionar={setDebito} />
          </div>
          <div className="flex flex-col gap-1.5 md:col-span-2">
            <Label>
              <span className="text-[var(--color-green)] font-bold mr-1">C</span>
              Conta crédito
            </Label>
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
