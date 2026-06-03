"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Drawer as DrawerPrimitive } from "vaul";
import { Lock, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "./logo";
import {
  GROUP_LABELS,
  SIDEBAR_ITEMS,
  moduloDisponivel,
  type SidebarItem,
} from "./nav-config";
import { useEmpresaAtual } from "./empresa-provider";
import { useUIStore } from "@/lib/stores/ui-store";

type GroupKey = SidebarItem["group"];
const GROUPS_ORDER: GroupKey[] = ["principal", "operacional", "ferramentas", "config"];

function indiceLabel(n: number): string {
  return String(n + 1).padStart(2, "0");
}

export function SidebarMobile() {
  const open = useUIStore((s) => s.sidebarMobileOpen);
  const setOpen = useUIStore((s) => s.setSidebarMobileOpen);
  const pathname = usePathname();
  const { empresa } = useEmpresaAtual();

  const itensPorGrupo = GROUPS_ORDER.map((g) => ({
    grupo: g,
    items: SIDEBAR_ITEMS.filter((i) => i.group === g),
  }));

  let contador = 0;

  return (
    <DrawerPrimitive.Root
      open={open}
      onOpenChange={setOpen}
      direction="left"
      shouldScaleBackground={false}
    >
      <DrawerPrimitive.Portal>
        <DrawerPrimitive.Overlay className="fixed inset-0 z-50 bg-[var(--color-ink)]/35 backdrop-blur-sm" />
        <DrawerPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-[272px] max-w-[82vw] flex-col outline-none",
            "text-[var(--color-ink)]"
          )}
          style={{
            background: "var(--color-paper-2)",
            borderRight: "1px solid var(--color-rule)",
          }}
        >
          <DrawerPrimitive.Title className="sr-only">
            Menu de navegação
          </DrawerPrimitive.Title>
          <div
            className="h-14 flex items-center justify-between gap-2.5 px-4 shrink-0"
            style={{ borderBottom: "1px solid var(--color-rule)" }}
          >
            <div className="flex items-center gap-2.5">
              <Logo size={26} />
              <div className="flex flex-col leading-none">
                <span className="font-[family-name:var(--font-serif)] text-[17px] font-semibold tracking-tight">
                  Arkan
                </span>
                <span className="mono text-[9px] uppercase tracking-[0.22em] text-[var(--color-ink-2)]">
                  Fiscal · Instrumento
                </span>
              </div>
            </div>
            <DrawerPrimitive.Close
              className="grid size-11 -mr-2 place-items-center text-[var(--color-ink-2)] hover:text-[var(--color-ink)] transition-colors"
              aria-label="Fechar menu"
            >
              <X className="size-4" />
            </DrawerPrimitive.Close>
          </div>

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
                      (item.href !== "/home" && pathname?.startsWith(item.href));

                    if (!disponivel) {
                      return (
                        <li key={item.id}>
                          <button
                            type="button"
                            disabled
                            className="flex w-full items-center gap-3 min-h-[44px] py-2 pl-1 pr-2 text-sm text-[var(--color-ink-3)] cursor-not-allowed opacity-70"
                          >
                            <span className="mono text-[10px] tabular-nums w-5 shrink-0">
                              {indice}
                            </span>
                            <item.icon className="size-4 shrink-0" />
                            <span className="flex-1 text-left truncate">{item.label}</span>
                            <Lock className="size-3 shrink-0" />
                          </button>
                        </li>
                      );
                    }

                    return (
                      <li key={item.id} className="relative">
                        <span
                          aria-hidden="true"
                          className="absolute left-0 top-2 bottom-2 w-[2px] transition-opacity"
                          style={{
                            background: "var(--color-green)",
                            opacity: ativo ? 1 : 0,
                          }}
                        />
                        <Link
                          href={item.href}
                          aria-current={ativo ? "page" : undefined}
                          onClick={() => setOpen(false)}
                          className={cn(
                            "group/row flex items-center gap-3 min-h-[44px] py-2 pl-3 pr-2 text-sm transition-colors",
                            ativo
                              ? "text-[var(--color-ink)] font-semibold"
                              : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
                          )}
                        >
                          <span
                            className={cn(
                              "mono text-[10px] tabular-nums w-5 shrink-0",
                              ativo ? "text-[var(--color-green)]" : "text-[var(--color-ink-2)]"
                            )}
                          >
                            {indice}
                          </span>
                          <item.icon
                            className={cn(
                              "size-4 shrink-0",
                              ativo ? "text-[var(--color-green)]" : "text-[var(--color-ink-2)]"
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

          <div
            className="px-4 py-3.5 flex flex-col gap-1 shrink-0"
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
        </DrawerPrimitive.Content>
      </DrawerPrimitive.Portal>
    </DrawerPrimitive.Root>
  );
}
