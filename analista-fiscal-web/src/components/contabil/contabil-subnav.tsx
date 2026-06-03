"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/contabil", label: "Balancete" },
  { href: "/contabil/lancamentos", label: "Livro Diário" },
  { href: "/contabil/encerramento", label: "Encerramento" },
];

export function ContabilSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-center gap-1 border-b"
      style={{ borderColor: "var(--color-rule)" }}
    >
      {ITENS.map((it) => {
        const ativo =
          it.href === "/contabil"
            ? pathname === "/contabil"
            : pathname?.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            className={cn(
              "relative px-3 py-2.5 text-[13px] font-medium transition-colors",
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
