"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ChevronsUpDown, Menu, Search, Sparkles, User2 } from "lucide-react";
import { Logo } from "./logo";
import { useEmpresaAtual } from "./empresa-provider";
import { sair } from "@/lib/auth";
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
  const router = useRouter();
  const { empresa, resetar } = useEmpresaAtual();
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const setAssistOpen = useUIStore((s) => s.setAssistenteSidebarOpen);
  const setSidebarOpen = useUIStore((s) => s.setSidebarMobileOpen);

  function sairDaConta() {
    sair();
    // replace (não push) para não permitir voltar ao painel autenticado.
    router.replace("/login");
  }

  return (
    <header
      className="h-14 flex items-center gap-3 px-4 md:px-6 sticky top-0 z-30"
      style={{
        background: "var(--color-glass)",
        backdropFilter: "blur(14px) saturate(1.4)",
        WebkitBackdropFilter: "blur(14px) saturate(1.4)",
        borderBottom: "1px solid var(--color-rule)",
      }}
    >
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        className="md:hidden grid size-11 -ml-1.5 place-items-center text-[var(--color-ink-2)] hover:text-[var(--color-ink)] transition-colors"
        aria-label="Abrir menu"
      >
        <Menu className="size-5" />
      </button>

      {/* Wordmark Arkan no mobile */}
      <div className="md:hidden flex items-center gap-2">
        <Logo size={24} />
        <span className="font-[family-name:var(--font-serif)] text-[16px] font-semibold tracking-tight text-[var(--color-ink)]">
          Arkan
        </span>
      </div>

      {/* Seletor de empresa (masthead, desktop) */}
      <div className="hidden md:flex items-center gap-2.5">
        <span className="mono text-[9px] uppercase tracking-[0.22em] text-[var(--color-ink-2)] font-semibold">
          Empresa
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger className="group flex items-center gap-2.5 py-1.5 transition-colors">
            <span
              aria-hidden="true"
              className="size-1.5"
              style={{ background: "var(--color-green)" }}
            />
            <span className="font-[family-name:var(--font-serif)] text-[15px] font-semibold text-[var(--color-ink)] max-w-[260px] truncate group-hover:text-[var(--color-green)] transition-colors">
              {empresa?.razaoSocial ?? "—"}
            </span>
            {empresa ? (
              <span className="mono text-[10px] text-[var(--color-ink-2)] tabular-nums">
                {formatarCNPJ(empresa.cnpj)}
              </span>
            ) : null}
            <ChevronsUpDown className="size-3.5 text-[var(--color-ink-3)]" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-[280px]">
            <DropdownMenuLabel>Empresas conectadas</DropdownMenuLabel>
            <DropdownMenuItem className="flex flex-col items-start gap-0.5">
              <span className="text-sm text-[var(--color-ink)] font-semibold">
                {empresa?.razaoSocial ?? "—"}
              </span>
              {empresa ? (
                <span className="mono text-[10px] text-[var(--color-ink-2)] tabular-nums">
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

      {/* Busca / command palette */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden md:flex items-center gap-2 px-3 h-11 text-sm transition-colors hover:border-[var(--color-rule-2)]"
        style={{
          background: "var(--color-card)",
          border: "1px solid var(--color-rule)",
          borderRadius: "var(--radius-md)",
          color: "var(--color-ink-2)",
        }}
      >
        <Search className="size-4" />
        <span>Buscar...</span>
        <kbd
          className="mono ml-2 text-[10px] px-1.5 py-0.5 text-[var(--color-ink-2)]"
          style={{ border: "1px solid var(--color-rule-2)", borderRadius: "var(--radius-sm)" }}
        >
          Ctrl K
        </kbd>
      </button>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="md:hidden grid size-11 place-items-center text-[var(--color-ink-2)] hover:text-[var(--color-ink)] transition-colors"
        aria-label="Buscar"
      >
        <Search className="size-4" />
      </button>

      {/* Assistente */}
      <button
        type="button"
        onClick={() => setAssistOpen(true)}
        className="flex items-center gap-1.5 h-11 px-3 mono text-[11px] uppercase tracking-[0.12em] font-semibold transition-colors hover:bg-[var(--color-green-wash)]"
        style={{
          background: "transparent",
          color: "var(--color-green-deep)",
          border: "1px solid var(--color-green)",
          borderRadius: "var(--radius-md)",
        }}
        aria-label="Abrir assistente"
      >
        <Sparkles className="size-3.5" />
        <span className="hidden sm:inline">Assistente</span>
      </button>

      {/* Conta */}
      <DropdownMenu>
        <DropdownMenuTrigger
          className="grid size-11 place-items-center transition-colors hover:border-[var(--color-rule-2)]"
          style={{
            background: "var(--color-card)",
            border: "1px solid var(--color-rule)",
            borderRadius: "var(--radius-md)",
          }}
          aria-label="Menu da conta"
        >
          <User2 className="size-4 text-[var(--color-ink-2)]" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[200px]">
          <DropdownMenuLabel>Sua conta</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => router.push("/configuracoes")}>
            Configurações
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-[var(--color-danger)]"
            onClick={sairDaConta}
          >
            Sair
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
