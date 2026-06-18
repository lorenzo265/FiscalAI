"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  MoreHorizontal,
  Plus,
  Search,
  X,
} from "lucide-react";
import { useQueryStates, parseAsString, parseAsInteger } from "nuqs";
import {
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { Moeda } from "@/components/shared/moeda";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { NotasSubnav } from "@/components/notas/notas-subnav";
import {
  ManifestoPill,
  StatusNotaPill,
  TipoNotaPill,
} from "@/components/notas/status-pill";
import { Framed } from "@/components/blueprint/framed";
import { useNotas } from "@/hooks/use-notas";
import { useCountUp } from "@/lib/motion/use-count-up";
import { baixarDANFE, baixarXml } from "@/lib/notas/downloads";
import { formatarDataBR } from "@/lib/format/data";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import { formatarMoeda } from "@/lib/format/moeda";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import type { NotaFiscal } from "@/lib/schemas/nota";

const PAGE_SIZE = 50;

/** Nome do mês corrente em PT (ex.: "junho") — locale-correto, sem índice inseguro. */
function mesAtual(): string {
  return new Intl.DateTimeFormat("pt-BR", { month: "long" }).format(new Date());
}

/** Soma valorNota das notas de saída autorizadas no mês corrente. */
function calcularFaturamentoMes(notas: NotaFiscal[]): number {
  const agora = new Date();
  const anoAtual = agora.getFullYear();
  const mesAtualIdx = agora.getMonth();

  return notas.reduce((soma, n) => {
    if (n.tipo !== "saida" || n.status !== "autorizada") return soma;
    const emitida = new Date(n.emitidaEm);
    if (
      emitida.getFullYear() === anoAtual &&
      emitida.getMonth() === mesAtualIdx
    ) {
      return soma + n.totais.valorNota;
    }
    return soma;
  }, 0);
}

/** Conta notas de saída autorizadas no mês corrente. */
function contarNotasMes(notas: NotaFiscal[]): number {
  const agora = new Date();
  const anoAtual = agora.getFullYear();
  const mesAtualIdx = agora.getMonth();

  return notas.filter((n) => {
    if (n.tipo !== "saida" || n.status !== "autorizada") return false;
    const emitida = new Date(n.emitidaEm);
    return (
      emitida.getFullYear() === anoAtual &&
      emitida.getMonth() === mesAtualIdx
    );
  }).length;
}

export default function NotasListaPage() {
  const { data, isLoading, isError, refetch } = useNotas();
  const reduced = useReducedMotion();

  const [filtros, setFiltros] = useQueryStates(
    {
      q: parseAsString.withDefault(""),
      tipo: parseAsString.withDefault("todos"),
      status: parseAsString.withDefault("todos"),
      periodo: parseAsString.withDefault("90d"),
      page: parseAsInteger.withDefault(0),
    },
    { history: "replace" }
  );

  /* ── métricas do herói ── */
  const faturamentoMes = React.useMemo(
    () => (data ? calcularFaturamentoMes(data) : 0),
    [data]
  );
  const notasMes = React.useMemo(
    () => (data ? contarNotasMes(data) : 0),
    [data]
  );

  /* count-up: anima o valor bruto em centavos para evitar decimal jitter */
  const faturamentoCentavos = Math.round(faturamentoMes * 100);
  const heroRaw = useCountUp(faturamentoCentavos, {
    id: "notas:faturamento-mes",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

  /* ── filtragem ── */
  const filtradas = React.useMemo<NotaFiscal[]>(() => {
    if (!data) return [];
    const corte = corteData(filtros.periodo);
    const q = filtros.q.trim().toLowerCase();
    return data.filter((n) => {
      if (filtros.tipo !== "todos" && n.tipo !== filtros.tipo) return false;
      if (filtros.status !== "todos" && n.status !== filtros.status)
        return false;
      if (corte && new Date(n.emitidaEm).getTime() < corte) return false;
      if (q) {
        const hay =
          `${n.numero} ${n.chave} ${n.contraparte.nome} ${n.contraparte.documento}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, filtros]);

  /* ── TanStack: paginação ── (DataTable renderiza; TanStack pagina) */
  const colunasTanStack = React.useMemo<ColumnDef<NotaFiscal>[]>(
    () => [{ id: "_placeholder", cell: () => null }],
    []
  );

  const table = useReactTable({
    data: filtradas,
    columns: colunasTanStack,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      pagination: { pageIndex: filtros.page, pageSize: PAGE_SIZE },
    },
    onPaginationChange: (updater) => {
      const next =
        typeof updater === "function"
          ? updater({ pageIndex: filtros.page, pageSize: PAGE_SIZE })
          : updater;
      void setFiltros({ page: next.pageIndex });
    },
  });

  /** Notas da página corrente (para o DataTable renderizar). */
  const paginaAtual = React.useMemo<NotaFiscal[]>(() => {
    const start = filtros.page * PAGE_SIZE;
    return filtradas.slice(start, start + PAGE_SIZE);
  }, [filtradas, filtros.page]);

  /* ── colunas DataTable ── */
  const colunas = React.useMemo<DataTableColumn<NotaFiscal>[]>(
    () => [
      {
        id: "contraparte",
        header: "Contraparte",
        primary: true,
        cell: (n) => (
          <div className="flex flex-col min-w-0">
            <span className="text-sm text-[var(--color-ink)] truncate font-medium">
              {n.contraparte.nome}
            </span>
            <span
              className="mono text-[11px] text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {n.contraparte.tipo === "pj"
                ? formatarCNPJ(n.contraparte.documento)
                : formatarCPF(n.contraparte.documento)}
            </span>
          </div>
        ),
      },
      {
        id: "tipo",
        header: "Tipo",
        cell: (n) => <TipoNotaPill tipo={n.tipo} />,
        width: "5rem",
      },
      {
        id: "numero",
        header: "Número",
        mono: true,
        // linha inteira navega (stretched-link); número é só dado, não link redundante
        cell: (n) => (
          <span
            className="mono text-sm font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {n.numero}
          </span>
        ),
        width: "7rem",
      },
      {
        id: "valor",
        header: "Valor",
        mono: true,
        align: "right",
        cell: (n) => (
          <span
            className="mono text-sm font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={n.totais.valorNota} />
          </span>
        ),
        width: "8.5rem",
      },
      {
        id: "data",
        header: "Emissão",
        mono: true,
        cell: (n) => (
          <span
            className="mono text-xs text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarDataBR(n.emitidaEm)}
          </span>
        ),
        width: "7rem",
      },
      {
        id: "status",
        header: "Status",
        cell: (n) => (
          <div className="flex items-center gap-1.5 flex-wrap">
            <StatusNotaPill status={n.status} />
            {n.tipo === "entrada" && n.manifesto ? (
              <ManifestoPill manifesto={n.manifesto} />
            ) : null}
          </div>
        ),
        width: "13rem",
      },
      {
        id: "acoes",
        header: "",
        hideLabelOnCard: true,
        // controles interativos: a DataTable iça esta célula acima do stretched-link
        interactive: true,
        cell: (n) => (
          <div className="flex items-center justify-end">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" className="size-8" aria-label="Ações da nota">
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => baixarDANFE(n)}>
                  <FileText className="size-3.5" /> Baixar DANFE (PDF)
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => baixarXml(n)}>
                  <Download className="size-3.5" /> Baixar XML
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href={`/notas/${n.chave}`}>Ver detalhe</Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ),
        width: "4rem",
      },
    ],
    []
  );

  const limparFiltros = () =>
    setFiltros({
      q: "",
      tipo: "todos",
      status: "todos",
      periodo: "90d",
      page: 0,
    });

  /* ── motion variants ── */
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
      {/* ── Bloco 1: cabeçalho + número-herói + ação primária ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4"
      >
        {/* linha superior: título + botão Emitir */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemVariants}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Módulo · Notas
            </motion.span>
            <motion.h1
              variants={itemVariants}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Notas fiscais
            </motion.h1>
          </div>

          {/* Ação primária — única, verde, 44px */}
          <motion.div variants={itemVariants} className="shrink-0 pt-5 md:pt-6">
            <Button asChild size="default" className="h-11 px-5 gap-2">
              <Link href="/notas/saida/nova">
                <Plus className="size-4" />
                Emitir nota
              </Link>
            </Button>
          </motion.div>
        </div>

        {/* número-herói: faturamento do mês corrente */}
        <motion.div variants={itemVariants} className="flex flex-col gap-1">
          <span
            className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
            style={{
              // piso 2.5rem cabe valores de 6–7 dígitos em 360–390px (mobile-first);
              // teto 4.5rem (72px) no desktop. Sobe suave no meio via vw.
              fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
              fontWeight: 300,
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.02em",
            }}
            aria-label={`Faturamento: ${heroFormatado}`}
          >
            {heroFormatado}
          </span>
          <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
            faturado em{" "}
            <span className="text-[var(--color-ink)]">{mesAtual()}</span>
          </span>
          {notasMes > 0 ? (
            <span
              className="mono text-[11px] text-[var(--color-ink-3)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {notasMes} nota{notasMes !== 1 ? "s" : ""} emitida{notasMes !== 1 ? "s" : ""}
            </span>
          ) : null}
        </motion.div>
      </motion.header>

      {/* ── Bloco 2: subnav + filtros ── */}
      <div className="flex flex-col gap-3">
        <NotasSubnav />

        <Framed
          marks={false}
          tone="rule"
          surface="card"
          className="flex flex-col md:flex-row md:items-center gap-3"
        >
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
            <Input
              value={filtros.q}
              onChange={(e) => void setFiltros({ q: e.target.value, page: 0 })}
              placeholder="Buscar por contraparte, CNPJ ou número"
              className="pl-9"
            />
          </div>
          <Select
            value={filtros.tipo}
            onValueChange={(v) => void setFiltros({ tipo: v, page: 0 })}
          >
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue placeholder="Tipo" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Tipo: todos</SelectItem>
              <SelectItem value="saida">Saída</SelectItem>
              <SelectItem value="entrada">Entrada</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filtros.status}
            onValueChange={(v) => void setFiltros({ status: v, page: 0 })}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Status: todos</SelectItem>
              <SelectItem value="autorizada">Autorizadas</SelectItem>
              <SelectItem value="cancelada">Canceladas</SelectItem>
              <SelectItem value="rejeitada">Rejeitadas</SelectItem>
              <SelectItem value="emitida">Em processamento</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filtros.periodo}
            onValueChange={(v) => void setFiltros({ periodo: v, page: 0 })}
          >
            <SelectTrigger className="w-full md:w-[140px]">
              <SelectValue placeholder="Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="30d">30 dias</SelectItem>
              <SelectItem value="90d">90 dias</SelectItem>
              <SelectItem value="180d">6 meses</SelectItem>
              <SelectItem value="365d">12 meses</SelectItem>
              <SelectItem value="todos">Todos</SelectItem>
            </SelectContent>
          </Select>
          {(filtros.q ||
            filtros.tipo !== "todos" ||
            filtros.status !== "todos" ||
            filtros.periodo !== "90d") && (
            <Button variant="ghost" size="sm" onClick={limparFiltros}>
              <X className="size-3.5" /> Limpar
            </Button>
          )}
        </Framed>
      </div>

      {/* ── Bloco 3: conteúdo principal ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando notas..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : filtradas.length === 0 ? (
        <EmptyState
          titulo="Nenhuma nota encontrada"
          descricao="Ajuste os filtros ou emita uma nova nota fiscal."
          icone={FileText}
        />
      ) : (
        /* Painel plano v2: sem crop marks, borda 1px rule, radius 10px */
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
          {/* label de seção (Hanken) — sem a assinatura "Fig.", que recuou na v2 */}
          <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Registro de notas
            </h2>
          </div>

          {/* DataTable: tabela no md+, card no mobile */}
          <DataTable<NotaFiscal>
            data={paginaAtual}
            columns={colunas}
            getRowKey={(n) => n.chave}
            getRowHref={(n) => `/notas/${n.chave}`}
            getRowLabel={(n) => `Nota ${n.numero} — ${n.contraparte.nome}`}
            caption="Registro de notas fiscais"
          />

          {/* paginação */}
          <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-[var(--color-rule)]">
            <span
              className="text-xs text-[var(--color-ink-3)] mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {filtradas.length} nota(s) · página{" "}
              {table.getState().pagination.pageIndex + 1} de{" "}
              {table.getPageCount()}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
              >
                <ChevronLeft className="size-3.5" /> Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
              >
                Próxima <ChevronRight className="size-3.5" />
              </Button>
            </div>
          </div>
        </Framed>
      )}
    </motion.div>
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
