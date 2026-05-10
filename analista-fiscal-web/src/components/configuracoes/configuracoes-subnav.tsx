"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITENS = [
  { href: "/configuracoes", label: "Visão geral" },
  { href: "/configuracoes/empresa", label: "Empresa" },
  { href: "/configuracoes/certificado", label: "Certificado" },
  { href: "/configuracoes/integracoes", label: "Integrações" },
  { href: "/configuracoes/usuarios", label: "Usuários" },
];

export function ConfiguracoesSubnav() {
  const pathname = usePathname();
  return (
    <nav
      className="flex items-center gap-1 border-b overflow-x-auto"
      style={{ borderColor: "var(--color-line)" }}
    >
      {ITENS.map((it) => {
        const ativo =
          it.href === "/configuracoes"
            ? pathname === "/configuracoes"
            : pathname?.startsWith(it.href);
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
