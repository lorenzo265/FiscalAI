"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/notas", label: "Todas as notas", indice: "01" },
  { href: "/notas/entrada", label: "Entradas (manifesto)", indice: "02" },
  { href: "/notas/saida/nova", label: "Emitir nova nota", indice: "03", destaque: true },
];

/**
 * NotasSubnav — subnav na linguagem do shell Arkan:
 * índice mono + underline verde no ativo, sem pílulas.
 * "Emitir nova nota" alinhado à direita com acento verde sutil (borda, não fundo lavado).
 */
export function NotasSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-end gap-0 border-b"
      style={{ borderColor: "var(--color-rule)" }}
      aria-label="Sub-navegação de notas"
    >
      {ITENS.map((it) => {
        const ativo =
          it.href === "/notas"
            ? pathname === "/notas"
            : pathname?.startsWith(it.href);

        if (it.destaque) {
          return (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "ml-auto relative flex items-center gap-1.5 px-3 py-2.5 text-[12px] font-semibold transition-colors",
                "mono uppercase tracking-[0.14em]",
                ativo
                  ? "text-[var(--color-green)] border border-[var(--color-green)] border-b-0 bg-[var(--color-green-wash)] rounded-t-[var(--radius-md)]"
                  : "text-[var(--color-ink-2)] border border-transparent hover:text-[var(--color-green)] hover:border-[var(--color-green)] hover:border-b-0 hover:bg-[var(--color-green-wash)] hover:rounded-t-[var(--radius-md)]"
              )}
            >
              <span className="text-[10px] opacity-60">{it.indice}</span>
              + {it.label}
            </Link>
          );
        }

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
            {/* underline verde técnico no item ativo — fio 2px, sem rounded-full */}
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
