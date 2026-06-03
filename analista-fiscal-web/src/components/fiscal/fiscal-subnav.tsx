"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/fiscal", label: "Apuração", indice: "01" },
  { href: "/fiscal/guias", label: "Guias", indice: "02" },
  { href: "/fiscal/simulador", label: "Simulador", indice: "03" },
  { href: "/fiscal/reforma-tributaria", label: "Reforma 2026", indice: "04" },
];

/**
 * FiscalSubnav — subnav na linguagem do shell Arkan:
 * índice mono + underline verde no ativo, sem pílulas.
 * Espelha NotasSubnav (gabarito de ouro do Lote B).
 */
export function FiscalSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-end gap-0 border-b"
      style={{ borderColor: "var(--color-rule)" }}
      aria-label="Sub-navegação fiscal"
    >
      {ITENS.map((it) => {
        const ativo =
          it.href === "/fiscal"
            ? pathname === "/fiscal"
            : pathname?.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            aria-current={ativo ? "page" : undefined}
            className={cn(
              "relative flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-medium transition-colors",
              ativo
                ? "text-[var(--color-ink)]"
                : "text-[var(--color-ink-2)] hover:text-[var(--color-ink)]"
            )}
          >
            <span className="mono text-[10px] text-[var(--color-ink-3)] font-semibold">
              {it.indice}
            </span>
            {it.label}
            {ativo ? (
              <span
                className="absolute left-3 right-3 -bottom-px h-[2px]"
                style={{ background: "var(--color-green)" }}
                aria-hidden
              />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
