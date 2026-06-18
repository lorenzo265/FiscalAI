"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Wallet,
  Calendar,
  Menu,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui-store";

/**
 * BottomTabBar — navegação mobile da identidade Arkan "Claro" v2 (§3).
 * 4 destinos + "Mais": Visão geral · Notas · Pagar · Agenda · Mais.
 *
 * Vidro translúcido (`--color-glass` + blur), radius 16 (`--radius-lg`),
 * flutua 8px da base; ícone + palavra SEMPRE (nunca só ícone, nunca emoji).
 * Só aparece no mobile (`md:hidden`) — a sidebar desktop (Fase 2) permanece
 * intacta. "Mais" abre o drawer de navegação completo (mesma store do menu
 * hamburguer da topbar), então TODAS as rotas continuam acessíveis (invariante).
 *
 * As rotas/ícones reaproveitam a navegação existente (`nav-config`): home,
 * notas, agenda; "Pagar" aponta para /controles/pagar (já existente). Nada
 * de rota nova.
 */

type TabDestino = {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Casa também sub-rotas (ex.: /notas/[chave]). */
  match: (pathname: string) => boolean;
};

const DESTINOS: TabDestino[] = [
  {
    label: "Visão geral",
    href: "/home",
    icon: LayoutDashboard,
    match: (p) => p === "/home" || p === "/",
  },
  {
    label: "Notas",
    href: "/notas",
    icon: FileText,
    match: (p) => p.startsWith("/notas"),
  },
  {
    label: "Pagar",
    href: "/controles/pagar",
    icon: Wallet,
    match: (p) => p.startsWith("/controles"),
  },
  {
    label: "Agenda",
    href: "/agenda",
    icon: Calendar,
    match: (p) => p.startsWith("/agenda"),
  },
];

export function BottomTabBar() {
  const pathname = usePathname() ?? "";
  const setSidebarOpen = useUIStore((s) => s.setSidebarMobileOpen);
  const sidebarOpen = useUIStore((s) => s.sidebarMobileOpen);

  return (
    <nav
      aria-label="Navegação principal"
      className="md:hidden fixed inset-x-0 bottom-0 z-40 px-3 pb-2 pt-0"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
    >
      <div
        className="mx-auto flex max-w-md items-stretch gap-0.5 rounded-[var(--radius-lg)] p-1"
        style={{
          background: "var(--color-glass)",
          backdropFilter: "blur(16px) saturate(1.4)",
          WebkitBackdropFilter: "blur(16px) saturate(1.4)",
          border: "1px solid var(--color-rule)",
        }}
      >
        {DESTINOS.map((d) => {
          const ativo = !sidebarOpen && d.match(pathname);
          return (
            <Link
              key={d.href}
              href={d.href}
              aria-current={ativo ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1.5 min-h-[48px] transition-colors",
                ativo
                  ? "text-[var(--color-green)]"
                  : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
              )}
            >
              <d.icon className="size-5 shrink-0" strokeWidth={1.75} aria-hidden />
              <span className="text-[10px] font-medium leading-none tracking-tight">
                {d.label}
              </span>
            </Link>
          );
        })}

        {/* "Mais" abre o drawer completo — mantém todas as rotas acessíveis */}
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          aria-haspopup="menu"
          aria-expanded={sidebarOpen}
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] px-1 py-1.5 min-h-[48px] transition-colors",
            sidebarOpen
              ? "text-[var(--color-green)]"
              : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
          )}
        >
          <Menu className="size-5 shrink-0" strokeWidth={1.75} aria-hidden />
          <span className="text-[10px] font-medium leading-none tracking-tight">Mais</span>
        </button>
      </div>
    </nav>
  );
}
