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
  Search,
  X,
} from "lucide-react";
import { useQueryStates, parseAsString, parseAsInteger } from "nuqs";
import {
  flexRender,
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
import { NotasSubnav } from "@/components/notas/notas-subnav";
import {
  ManifestoPill,
  StatusNotaPill,
  TipoNotaPill,
} from "@/components/notas/status-pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useNotas } from "@/hooks/use-notas";
import { baixarDANFE, baixarXml } from "@/lib/notas/downloads";
import { formatarDataBR } from "@/lib/format/data";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import type { NotaFiscal } from "@/lib/schemas/nota";

const PAGE_SIZE = 50;

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

  const colunas = React.useMemo<ColumnDef<NotaFiscal>[]>(
    () => [
      {
        id: "tipo",
        header: "Tipo",
        cell: ({ row }) => <TipoNotaPill tipo={row.original.tipo} />,
        size: 80,
      },
      {
        id: "numero",
        header: "Número",
        cell: ({ row }) => (
          <Link
            href={`/notas/${row.original.chave}`}
            className="mono text-sm font-bold text-[var(--color-ink)] hover:text-[var(--color-green)] transition-colors"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {row.original.numero}
          </Link>
        ),
        size: 110,
      },
      {
        id: "contraparte",
        header: "Contraparte",
        cell: ({ row }) => (
          <div className="flex flex-col min-w-0">
            <span className="text-sm text-[var(--color-ink)] truncate">
              {row.original.contraparte.nome}
            </span>
            <span
              className="mono text-[11px] text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {row.original.contraparte.tipo === "pj"
                ? formatarCNPJ(row.original.contraparte.documento)
                : formatarCPF(row.original.contraparte.documento)}
            </span>
          </div>
        ),
      },
      {
        id: "valor",
        header: "Valor",
        cell: ({ row }) => (
          <span
            className="mono text-sm font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={row.original.totais.valorNota} />
          </span>
        ),
        size: 130,
      },
      {
        id: "data",
        header: "Emissão",
        cell: ({ row }) => (
          <span
            className="mono text-xs text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarDataBR(row.original.emitidaEm)}
          </span>
        ),
        size: 110,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <div className="flex items-center gap-1.5 flex-wrap">
            <StatusNotaPill status={row.original.status} />
            {row.original.tipo === "entrada" && row.original.manifesto ? (
              <ManifestoPill manifesto={row.original.manifesto} />
            ) : null}
          </div>
        ),
        size: 200,
      },
      {
        id: "acoes",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-1">
            <Button asChild size="sm" variant="ghost">
              <Link href={`/notas/${row.original.chave}`}>Ver</Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" className="size-8">
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => baixarDANFE(row.original)}>
                  <FileText className="size-3.5" /> Baixar DANFE (PDF)
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => baixarXml(row.original)}>
                  <Download className="size-3.5" /> Baixar XML
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href={`/notas/${row.original.chave}`}>
                    Ver detalhe
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ),
        size: 130,
      },
    ],
    []
  );

  const table = useReactTable({
    data: filtradas,
    columns: colunas,
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

  const limparFiltros = () =>
    setFiltros({
      q: "",
      tipo: "todos",
      status: "todos",
      periodo: "90d",
      page: 0,
    });

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
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Notas
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Notas fiscais
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Tudo que entra e sai da sua empresa em um só lugar.
        </motion.p>
      </motion.header>

      <NotasSubnav />

      {/* ── filtros ── */}
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col md:flex-row md:items-center gap-3">
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

      {/* ── conteúdo principal ── */}
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
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          {/* Fig. 01 — Registro de notas */}
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo="Registro de notas" size="sm" />
          </div>
          <Ruler />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono"
                  style={{ borderColor: "var(--color-rule)" }}
                >
                  {table.getHeaderGroups()[0]?.headers.map((h) => (
                    <th key={h.id} className="px-4 py-3 font-bold">
                      {flexRender(
                        h.column.columnDef.header,
                        h.getContext()
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b transition-colors hover:bg-[var(--color-paper-2)]"
                    style={{ borderColor: "var(--color-rule)" }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3 align-middle">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Ruler />
          <div className="flex items-center justify-between gap-3 px-4 py-3">
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
