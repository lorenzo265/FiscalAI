"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/relatorios/dre", label: "DRE" },
  { href: "/relatorios/balanco", label: "Balanço" },
  { href: "/relatorios/dfc", label: "Fluxo de Caixa (DFC)" },
  { href: "/relatorios/indicadores", label: "Indicadores" },
];

export function RelatoriosSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-center gap-1 border-b overflow-x-auto"
      style={{ borderColor: "var(--color-line)" }}
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
                ? "text-[var(--color-txt)]"
                : "text-[var(--color-txt-2)] hover:text-[var(--color-txt)]"
            )}
          >
            {it.label}
            {ativo ? (
              <span
                className="absolute left-2 right-2 -bottom-px h-[2px] rounded-full"
                style={{ background: "var(--color-lime)" }}
              />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
