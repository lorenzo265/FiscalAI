"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/notas", label: "Todas as notas" },
  { href: "/notas/entrada", label: "Entradas (manifesto)" },
  { href: "/notas/saida/nova", label: "Emitir nova", destaque: true },
];

export function NotasSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-center gap-1 border-b"
      style={{ borderColor: "var(--color-line)" }}
    >
      {ITENS.map((it) => {
        const ativo =
          it.href === "/notas"
            ? pathname === "/notas"
            : pathname?.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            className={cn(
              "relative px-3 py-2.5 text-[13px] font-medium transition-colors",
              ativo
                ? "text-[var(--color-txt)]"
                : "text-[var(--color-txt-2)] hover:text-[var(--color-txt)]",
              it.destaque && "ml-auto"
            )}
          >
            {it.destaque ? (
              <span
                className={cn(
                  "px-2.5 py-1 rounded-md mono uppercase tracking-[0.12em] text-[11px] font-bold",
                  "bg-[var(--color-lime-d)] text-[var(--color-lime)] border border-[rgba(163,255,107,0.22)]"
                )}
              >
                + {it.label}
              </span>
            ) : (
              it.label
            )}
            {ativo && !it.destaque ? (
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
