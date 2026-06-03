"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/relatorios/dre", label: "DRE" },
  { href: "/relatorios/balanco", label: "Balanço" },
  { href: "/relatorios/dfc", label: "Fluxo de Caixa" },
  { href: "/relatorios/indicadores", label: "Indicadores" },
];

export function RelatoriosSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-center gap-1 border-b overflow-x-auto"
      style={{ borderColor: "var(--color-rule)" }}
    >
      {ITENS.map((it) => {
        const ativo = pathname?.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            className={cn(
              "relative px-3 py-2.5 text-[13px] font-medium transition-colors whitespace-nowrap",
              ativo
                ? "text-[var(--color-ink)]"
                : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
            )}
          >
            {it.label}
            {ativo ? (
              <span
                className="absolute left-2 right-2 -bottom-px h-[2px] rounded-[var(--radius-sm)]"
                style={{ background: "var(--color-green)" }}
              />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
