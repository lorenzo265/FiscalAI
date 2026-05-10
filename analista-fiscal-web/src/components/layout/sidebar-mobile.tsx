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

export function SidebarMobile() {
  const open = useUIStore((s) => s.sidebarMobileOpen);
  const setOpen = useUIStore((s) => s.setSidebarMobileOpen);
  const pathname = usePathname();
  const { empresa } = useEmpresaAtual();

  const itensPorGrupo = GROUPS_ORDER.map((g) => ({
    grupo: g,
    items: SIDEBAR_ITEMS.filter((i) => i.group === g),
  }));

  return (
    <DrawerPrimitive.Root
      open={open}
      onOpenChange={setOpen}
      direction="left"
      shouldScaleBackground={false}
    >
      <DrawerPrimitive.Portal>
        <DrawerPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm" />
        <DrawerPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-[260px] max-w-[80vw] flex-col border-r outline-none",
            "bg-[var(--color-bg-2)] text-[var(--color-txt)] border-[var(--color-line)]"
          )}
        >
          <DrawerPrimitive.Title className="sr-only">
            Menu de navegação
          </DrawerPrimitive.Title>
          <div className="h-14 flex items-center justify-between gap-2.5 px-4 border-b border-[var(--color-line)] shrink-0">
            <div className="flex items-center gap-2.5">
              <Logo size={26} />
              <span className="font-bold text-sm tracking-tight">FiscalAI</span>
            </div>
            <DrawerPrimitive.Close
              className="p-1.5 rounded-md text-[var(--color-txt-3)] hover:text-[var(--color-txt)] hover:bg-[var(--color-card-2)] transition-colors"
              aria-label="Fechar menu"
            >
              <X className="size-4" />
            </DrawerPrimitive.Close>
          </div>

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
                    (item.href !== "/home" && pathname?.startsWith(item.href));

                  if (!disponivel) {
                    return (
                      <button
                        key={item.id}
                        type="button"
                        disabled
                        className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm text-[var(--color-txt-3)] cursor-not-allowed opacity-60"
                      >
                        <item.icon className="size-4" />
                        <span className="flex-1 text-left">{item.label}</span>
                        <Lock className="size-3" />
                      </button>
                    );
                  }

                  return (
                    <Link
                      key={item.id}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className={cn(
                        "flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors",
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

          <div className="p-3 border-t border-[var(--color-line)] shrink-0">
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
        </DrawerPrimitive.Content>
      </DrawerPrimitive.Portal>
    </DrawerPrimitive.Root>
  );
}
