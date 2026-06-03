"use client";

import Link from "next/link";
import {
  ArrowRight,
  FileText,
  Sparkles,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";

interface Atalho {
  label: string;
  descricao: string;
  href: string;
  icon: LucideIcon;
  indice: string;
}

const ATALHOS: Atalho[] = [
  {
    label: "Emitir NF-e",
    descricao: "Em 4 passos curtos.",
    href: "/notas/saida/nova",
    icon: FileText,
    indice: "01",
  },
  {
    label: "Ver folha",
    descricao: "Holerites do mês.",
    href: "/pessoal",
    icon: Users,
    indice: "02",
  },
  {
    label: "Ver fluxo de caixa",
    descricao: "Projeção 90 dias.",
    href: "/controles",
    icon: Wallet,
    indice: "03",
  },
  {
    label: "Falar com o assistente",
    descricao: "Pergunte sobre seus impostos.",
    href: "/assistente",
    icon: Sparkles,
    indice: "04",
  },
];

export function QuickActions() {
  return (
    <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
      {/* cabeçalho */}
      <div className="px-5 pt-4 pb-2">
        <Fig n="A" titulo="Atalhos rápidos" size="sm" />
      </div>
      <Ruler />

      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0" style={{ borderColor: "var(--color-rule)" }}>
        {ATALHOS.map((a) => (
          <Link
            key={a.href}
            href={a.href}
            className="group p-4 flex flex-col gap-3 transition-colors hover:bg-[var(--color-paper-2)]"
          >
            {/* índice técnico */}
            <span className="mono text-[10px] font-semibold text-[var(--color-ink-3)] uppercase tracking-[0.14em]">
              {a.indice}
            </span>
            {/* ícone — quadrado técnico */}
            <span
              className="size-8 rounded-[var(--radius-md)] grid place-items-center border"
              style={{
                background: "var(--color-paper-2)",
                borderColor: "var(--color-rule-2)",
              }}
            >
              <a.icon className="size-4 text-[var(--color-green)]" aria-hidden />
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-[var(--color-ink)] flex items-center gap-1.5">
                {a.label}
                <ArrowRight className="size-3 opacity-0 group-hover:opacity-100 transition-opacity text-[var(--color-green)]" />
              </span>
              <span className="text-[11px] text-[var(--color-ink-2)] leading-snug">
                {a.descricao}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </Framed>
  );
}
