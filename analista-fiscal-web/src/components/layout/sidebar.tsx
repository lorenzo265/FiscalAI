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

  return (
    <aside
      className="hidden md:flex md:w-[224px] flex-col border-r"
      style={{
        background: "var(--color-bg-2)",
        borderColor: "var(--color-line)",
      }}
    >
      <div className="h-14 flex items-center gap-2.5 px-4 border-b border-[var(--color-line)]">
        <Logo size={28} />
        <div className="flex flex-col leading-none">
          <span className="text-sm font-bold tracking-tight text-[var(--color-txt)]">
            FiscalAI
          </span>
          <span className="mono text-[9px] uppercase tracking-[0.18em] text-[var(--color-txt-3)]">
            v0.1
          </span>
        </div>
      </div>

      <TooltipProvider delayDuration={200}>
        <nav className="flex-1 overflow-y-auto py-3 px-2 flex flex-col gap-4">
          {itensPorGrupo.map(({ grupo, items }) => (
            <div key={grupo} className="flex flex-col gap-0.5">
              <span className="px-2 py-1 text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-txt-3)]">
                {GROUP_LABELS[grupo]}
              </span>
              {items.map((item) => {
                const disponivel = empresa
                  ? moduloDisponivel(item.id, empresa.regime)
                  : true;
                const ativo =
                  pathname === item.href ||
                  (item.href !== "/home" && pathname.startsWith(item.href));

                if (!disponivel) {
                  return (
                    <Tooltip key={item.id}>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm text-[var(--color-txt-3)] cursor-not-allowed opacity-60"
                        >
                          <item.icon className="size-4" />
                          <span className="flex-1 text-left">{item.label}</span>
                          <Lock className="size-3" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right">
                        Disponível em planos superiores
                      </TooltipContent>
                    </Tooltip>
                  );
                }

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onPointerEnter={() => prefetch(item.id)}
                    onFocus={() => prefetch(item.id)}
                    className={cn(
                      "flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors",
                      ativo
                        ? "bg-[var(--color-lime-d)] text-[var(--color-lime)] font-semibold"
                        : "text-[var(--color-txt-2)] hover:text-[var(--color-txt)] hover:bg-[var(--color-card-2)]"
                    )}
                  >
                    <item.icon className="size-4" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </TooltipProvider>

      <div className="p-3 border-t border-[var(--color-line)]">
        <div
          className="rounded-md p-3 flex flex-col gap-1"
          style={{ background: "var(--color-card)" }}
        >
          <span className="text-[9px] uppercase tracking-[0.18em] font-bold text-[var(--color-txt-3)]">
            Empresa
          </span>
          <span className="text-sm font-semibold text-[var(--color-txt)] truncate">
            {empresa?.razaoSocial ?? "Sem empresa"}
          </span>
          {empresa ? (
            <span className="mono text-[10px] text-[var(--color-txt-2)]">
              {empresa.regime === "SIMPLES_NACIONAL"
                ? `Simples · Anexo ${empresa.anexoSimples ?? "—"}`
                : empresa.regime}
            </span>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
