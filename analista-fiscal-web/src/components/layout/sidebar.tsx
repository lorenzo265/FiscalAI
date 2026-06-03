"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Logo } from "./logo";
import {
  GROUP_LABELS,
  SIDEBAR_ITEMS,
  moduloDisponivel,
  type SidebarItem,
} from "./nav-config";
import { useEmpresaAtual } from "./empresa-provider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { prefetchModulo } from "@/lib/prefetch";

type GroupKey = SidebarItem["group"];

const GROUPS_ORDER: GroupKey[] = ["principal", "operacional", "ferramentas", "config"];

/** Índice mono contínuo 01..N na ordem visual da navegação. */
function indiceLabel(n: number): string {
  return String(n + 1).padStart(2, "0");
}

export function Sidebar() {
  const pathname = usePathname();
  const { empresa } = useEmpresaAtual();
  const qc = useQueryClient();
  const prefetched = React.useRef<Set<string>>(new Set());

  const prefetch = React.useCallback(
    (moduloId: SidebarItem["id"]) => {
      if (!empresa) return;
      if (prefetched.current.has(moduloId)) return;
      prefetched.current.add(moduloId);
      void prefetchModulo(qc, moduloId, empresa);
    },
    [empresa, qc]
  );

  const itensPorGrupo = GROUPS_ORDER.map((g) => ({
    grupo: g,
    items: SIDEBAR_ITEMS.filter((i) => i.group === g),
  }));

  // Índice contínuo respeitando a ordem dos grupos.
  let contador = 0;

  return (
    <aside
      className="hidden md:flex md:w-[232px] flex-col"
      style={{
        background: "var(--color-paper-2)",
        borderRight: "1px solid var(--color-rule)",
      }}
    >
      {/* Masthead da sidemenu — selo + wordmark Arkan */}
      <div
        className="h-14 flex items-center gap-2.5 px-4"
        style={{ borderBottom: "1px solid var(--color-rule)" }}
      >
        <Logo size={26} />
        <div className="flex flex-col leading-none">
          <span className="font-[family-name:var(--font-serif)] text-[17px] font-semibold tracking-tight text-[var(--color-ink)]">
            Arkan
          </span>
          <span className="mono text-[9px] uppercase tracking-[0.22em] text-[var(--color-ink-2)]">
            Fiscal · Instrumento
          </span>
        </div>
      </div>

      <TooltipProvider delayDuration={200}>
        <nav className="flex-1 overflow-y-auto py-4 px-3 flex flex-col gap-5">
          {itensPorGrupo.map(({ grupo, items }) => (
            <div key={grupo} className="flex flex-col">
              <span className="mono px-1 pb-2 text-[9px] uppercase tracking-[0.22em] font-semibold text-[var(--color-ink-2)]">
                {GROUP_LABELS[grupo]}
              </span>
              <ul className="flex flex-col">
                {items.map((item) => {
                  const indice = indiceLabel(contador);
                  contador += 1;

                  const disponivel = empresa
                    ? moduloDisponivel(item.id, empresa.regime)
                    : true;
                  const ativo =
                    pathname === item.href ||
                    (item.href !== "/home" && pathname.startsWith(item.href));

                  if (!disponivel) {
                    return (
                      <li key={item.id}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="group/row flex w-full items-center gap-3 py-2 pl-1 pr-2 text-sm text-[var(--color-ink-3)] cursor-not-allowed opacity-70"
                            >
                              <span className="mono text-[10px] tabular-nums text-[var(--color-ink-3)] w-5 shrink-0">
                                {indice}
                              </span>
                              <item.icon className="size-4 shrink-0" />
                              <span className="flex-1 text-left truncate">{item.label}</span>
                              <Lock className="size-3 shrink-0" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="right">
                            Disponível em planos superiores
                          </TooltipContent>
                        </Tooltip>
                      </li>
                    );
                  }

                  return (
                    <li key={item.id} className="relative">
                      {/* marcador verde de item ativo (fio, não pílula) */}
                      <span
                        aria-hidden="true"
                        className="absolute left-0 top-1.5 bottom-1.5 w-[2px] transition-opacity"
                        style={{
                          background: "var(--color-green)",
                          opacity: ativo ? 1 : 0,
                        }}
                      />
                      <Link
                        href={item.href}
                        aria-current={ativo ? "page" : undefined}
                        onPointerEnter={() => prefetch(item.id)}
                        onFocus={() => prefetch(item.id)}
                        className={cn(
                          "group/row flex items-center gap-3 py-2 pl-3 pr-2 text-sm transition-colors",
                          ativo
                            ? "text-[var(--color-ink)] font-semibold"
                            : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
                        )}
                      >
                        <span
                          className={cn(
                            "mono text-[10px] tabular-nums w-5 shrink-0 transition-colors",
                            ativo
                              ? "text-[var(--color-green)]"
                              : "text-[var(--color-ink-2)] group-hover/row:text-[var(--color-ink)]"
                          )}
                        >
                          {indice}
                        </span>
                        <item.icon
                          className={cn(
                            "size-4 shrink-0 transition-colors",
                            ativo
                              ? "text-[var(--color-green)]"
                              : "text-[var(--color-ink-2)] group-hover/row:text-[var(--color-ink)]"
                          )}
                        />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </TooltipProvider>

      {/* Rodapé — empresa em mono, com fio de separação */}
      <div
        className="px-4 py-3.5 flex flex-col gap-1"
        style={{ borderTop: "1px solid var(--color-rule)" }}
      >
        <span className="mono text-[9px] uppercase tracking-[0.22em] font-semibold text-[var(--color-ink-2)]">
          Empresa
        </span>
        <span className="font-[family-name:var(--font-serif)] text-sm font-semibold text-[var(--color-ink)] truncate leading-snug">
          {empresa?.razaoSocial ?? "Sem empresa"}
        </span>
        {empresa ? (
          <span className="mono text-[10px] text-[var(--color-ink-2)] tabular-nums">
            {empresa.regime === "SIMPLES_NACIONAL"
              ? `Simples · Anexo ${empresa.anexoSimples ?? "—"}`
              : empresa.regime}
          </span>
        ) : null}
      </div>
    </aside>
  );
}
