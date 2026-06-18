"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * DataTable — lista/tabela responsiva da identidade Arkan "Claro" v2 (§3).
 *
 * A REGRA "no mobile a tabela vira card" é responsabilidade DESTA primitiva, não
 * de cada tela: em `md+` renderiza uma tabela com **fios horizontais 1px apenas**;
 * abaixo de `md` cada linha vira um **card** (rótulo + valor empilhados). Linha
 * inteira clicável (com chevron) quando há `href`/`onRowClick`; hover = fundo
 * `paper-2`, sem borda nova. Dados em mono ficam por conta de cada coluna
 * (`mono: true` ou className), conforme o invariante "mono em todo dado".
 *
 * Aditivo: não substitui as listas `<ul>`/`Framed` existentes. As telas que hoje
 * usam tabela crua (`<table>`) ou querem o padrão tabela↔card podem adotá-la.
 *
 * Exemplo:
 *   <DataTable
 *     data={contas}
 *     getRowKey={(c) => c.id}
 *     getRowHref={(c) => `/controles/${c.id}`}
 *     columns={[
 *       { id: "venc", header: "Vencimento", cell: (c) => <DataBR data={c.vencimento} />, mono: true },
 *       { id: "desc", header: "Descrição", cell: (c) => c.descricao, primary: true },
 *       { id: "valor", header: "Valor", cell: (c) => <Moeda valor={c.valor} />, align: "right", mono: true },
 *     ]}
 *   />
 */
export interface DataTableColumn<T> {
  /** Chave estável da coluna. */
  id: string;
  /** Cabeçalho (desktop) / rótulo (card mobile). */
  header: React.ReactNode;
  /** Conteúdo da célula para a linha `row`. */
  cell: (row: T) => React.ReactNode;
  /** Alinhamento horizontal (desktop). Default "left". */
  align?: "left" | "right" | "center";
  /** Dado tabular: aplica `.mono` na célula. */
  mono?: boolean;
  /** É a coluna "título" da linha — vira destaque no card mobile. */
  primary?: boolean;
  /** Esconde o rótulo no card mobile (ex.: a coluna primária). */
  hideLabelOnCard?: boolean;
  /** Largura fixa da coluna (desktop), ex.: "8rem". */
  width?: string;
  /** className extra na célula. */
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: DataTableColumn<T>[];
  getRowKey: (row: T, index: number) => string;
  /** Linha inteira vira link (mostra chevron). */
  getRowHref?: (row: T) => string | undefined;
  /** Linha inteira clicável (mostra chevron). Ignorado se houver href. */
  onRowClick?: (row: T) => void;
  /** Rótulo acessível da tabela. */
  caption?: string;
  className?: string;
}

function alignClass(align: DataTableColumn<unknown>["align"]): string {
  if (align === "right") return "text-right";
  if (align === "center") return "text-center";
  return "text-left";
}

export function DataTable<T>({
  data,
  columns,
  getRowKey,
  getRowHref,
  onRowClick,
  caption,
  className,
}: DataTableProps<T>) {
  const interactive = Boolean(getRowHref || onRowClick);
  const primaryCol = columns.find((c) => c.primary) ?? columns[0];

  return (
    <div className={cn("w-full", className)}>
      {/* ── Desktop: tabela com fios horizontais 1px ── */}
      <table className="hidden md:table w-full border-collapse text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr style={{ borderBottom: "1px solid var(--color-rule)" }}>
            {columns.map((col) => (
              <th
                key={col.id}
                scope="col"
                style={col.width ? { width: col.width } : undefined}
                className={cn(
                  "mono px-4 py-2.5 text-[10px] uppercase tracking-[0.12em] font-semibold text-[var(--color-ink-2)]",
                  alignClass(col.align)
                )}
              >
                {col.header}
              </th>
            ))}
            {interactive ? <th className="w-10" aria-hidden /> : null}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const href = getRowHref?.(row);
            const rowKey = getRowKey(row, i);
            const handleClick = onRowClick ? () => onRowClick(row) : undefined;
            return (
              <tr
                key={rowKey}
                onClick={href ? undefined : handleClick}
                className={cn(
                  "group/row",
                  // `relative` ancora o stretched-link (::after) à LINHA inteira
                  href && "relative",
                  interactive && "cursor-pointer hover:bg-[var(--color-paper-2)] transition-colors"
                )}
                style={{ borderBottom: "1px solid var(--color-rule)" }}
              >
                {columns.map((col, ci) => {
                  const content = col.cell(row);
                  const cellInner =
                    href && ci === 0 ? (
                      // o link cobre a LINHA via ::after (stretched link)
                      <Link
                        href={href}
                        className="after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-[var(--color-green)]/45 focus-visible:after:ring-inset"
                      >
                        {content}
                      </Link>
                    ) : (
                      content
                    );
                  return (
                    <td
                      key={col.id}
                      className={cn(
                        "px-4 py-3 align-middle text-[var(--color-ink)]",
                        col.mono && "mono tabular-nums",
                        alignClass(col.align),
                        col.className
                      )}
                    >
                      {cellInner}
                    </td>
                  );
                })}
                {interactive ? (
                  <td className="px-2 text-right align-middle">
                    <ChevronRight className="inline size-4 text-[var(--color-ink-3)] group-hover/row:text-[var(--color-ink-2)] transition-colors" />
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* ── Mobile: cada linha vira card ── */}
      <ul className="md:hidden flex flex-col gap-2">
        {data.map((row, i) => {
          const href = getRowHref?.(row);
          const rowKey = getRowKey(row, i);
          const handleClick = onRowClick ? () => onRowClick(row) : undefined;

          const card = (
            <div
              className={cn(
                "rounded-[var(--radius-md)] border bg-[var(--color-card)] border-[var(--color-rule)] p-3 flex flex-col gap-2",
                interactive && "transition-colors hover:bg-[var(--color-paper-2)]"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 text-[var(--color-ink)] text-sm font-medium">
                  {primaryCol ? primaryCol.cell(row) : null}
                </div>
                {interactive ? (
                  <ChevronRight className="size-4 shrink-0 text-[var(--color-ink-3)]" />
                ) : null}
              </div>
              <dl className="flex flex-col gap-1">
                {columns
                  .filter((c) => c !== primaryCol)
                  .map((col) => (
                    <div key={col.id} className="flex items-baseline justify-between gap-3">
                      {!col.hideLabelOnCard ? (
                        <dt className="mono text-[10px] uppercase tracking-[0.1em] text-[var(--color-ink-2)] shrink-0">
                          {col.header}
                        </dt>
                      ) : null}
                      <dd
                        className={cn(
                          "min-w-0 text-right text-[var(--color-ink)]",
                          col.mono && "mono tabular-nums",
                          col.className
                        )}
                      >
                        {col.cell(row)}
                      </dd>
                    </div>
                  ))}
              </dl>
            </div>
          );

          return (
            <li key={rowKey}>
              {href ? (
                <Link href={href} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/45 rounded-[var(--radius-md)]">
                  {card}
                </Link>
              ) : handleClick ? (
                <button type="button" onClick={handleClick} className="block w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/45 rounded-[var(--radius-md)]">
                  {card}
                </button>
              ) : (
                card
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
