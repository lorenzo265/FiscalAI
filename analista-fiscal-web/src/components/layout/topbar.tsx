"use client";

import * as React from "react";
import { ChevronsUpDown, Menu, Search, Sparkles, User2 } from "lucide-react";
import { Logo } from "./logo";
import { useEmpresaAtual } from "./empresa-provider";
import { useUIStore } from "@/lib/stores/ui-store";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatarCNPJ } from "@/lib/format/cnpj";

export function Topbar() {
  const { empresa, resetar } = useEmpresaAtual();
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const setAssistOpen = useUIStore((s) => s.setAssistenteSidebarOpen);
  const setSidebarOpen = useUIStore((s) => s.setSidebarMobileOpen);

  return (
    <header
      className="h-14 flex items-center gap-3 px-4 md:px-6 border-b sticky top-0 z-30"
      style={{
        background: "var(--color-bg-2)",
        borderColor: "var(--color-line)",
      }}
    >
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        className="md:hidden p-2 -ml-1 rounded-md text-[var(--color-txt-2)] hover:text-[var(--color-txt)] hover:bg-[var(--color-card-2)] transition-colors"
        aria-label="Abrir menu"
      >
        <Menu className="size-5" />
      </button>

      <div className="md:hidden flex items-center gap-2">
        <Logo size={26} />
        <span className="font-bold text-sm">FiscalAI</span>
      </div>

      <div className="hidden md:flex items-center gap-2">
        <span className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Empresa
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 px-2.5 py-1.5 rounded-md transition-colors hover:bg-[var(--color-card-2)]">
            <span className="text-sm font-semibold text-[var(--color-txt)] max-w-[260px] truncate">
              {empresa?.razaoSocial ?? "—"}
            </span>
            {empresa ? (
              <span className="mono text-[10px] text-[var(--color-txt-3)]">
                {formatarCNPJ(empresa.cnpj)}
              </span>
            ) : null}
            <ChevronsUpDown className="size-3.5 text-[var(--color-txt-3)]" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-[280px]">
            <DropdownMenuLabel>Empresas conectadas</DropdownMenuLabel>
            <DropdownMenuItem className="flex flex-col items-start gap-0.5">
              <span className="text-sm text-[var(--color-txt)] font-semibold">
                {empresa?.razaoSocial ?? "—"}
              </span>
              {empresa ? (
                <span className="mono text-[10px] text-[var(--color-txt-3)]">
                  {formatarCNPJ(empresa.cnpj)} · {empresa.regime}
                </span>
              ) : null}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => void resetar()}>
              Resetar dados de demo
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex-1" />

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden md:flex items-center gap-2 px-3 h-9 rounded-md border text-sm transition-colors"
        style={{
          background: "var(--color-card)",
          borderColor: "var(--color-line-2)",
          color: "var(--color-txt-2)",
        }}
      >
        <Search className="size-4" />
        <span>Buscar...</span>
        <kbd className="mono ml-2 text-[10px] px-1.5 py-0.5 rounded border border-[var(--color-line-2)] text-[var(--color-txt-3)]">
          Ctrl K
        </kbd>
      </button>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="md:hidden p-2 rounded-md text-[var(--color-txt-2)] hover:bg-[var(--color-card-2)]"
        aria-label="Buscar"
      >
        <Search className="size-4" />
      </button>

      <button
        type="button"
        onClick={() => setAssistOpen(true)}
        className="flex items-center gap-1.5 h-9 px-3 rounded-md mono text-[11px] uppercase tracking-[0.12em] font-bold transition-colors"
        style={{
          background: "var(--color-lime-d)",
          color: "var(--color-lime)",
          borderColor: "rgba(163, 255, 107, 0.22)",
          borderWidth: 1,
          borderStyle: "solid",
        }}
      >
        <Sparkles className="size-3.5" />
        Assistente
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger
          className="size-9 rounded-full grid place-items-center border"
          style={{
            background: "var(--color-card)",
            borderColor: "var(--color-line-2)",
          }}
          aria-label="Menu da conta"
        >
          <User2 className="size-4 text-[var(--color-txt-2)]" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[200px]">
          <DropdownMenuLabel>Sua conta</DropdownMenuLabel>
          <DropdownMenuItem>Perfil</DropdownMenuItem>
          <DropdownMenuItem>Preferências</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-[var(--color-red)]">Sair</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
