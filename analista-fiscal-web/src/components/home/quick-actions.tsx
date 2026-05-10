"use client";

import Link from "next/link";
import { ArrowRight, FileText, Sparkles, Users, Wallet, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

interface Atalho {
  label: string;
  descricao: string;
  href: string;
  icon: LucideIcon;
  cor: string;
  fundoCor: string;
}

const ATALHOS: Atalho[] = [
  {
    label: "Emitir NF-e",
    descricao: "Em 4 passos curtos.",
    href: "/notas/saida/nova",
    icon: FileText,
    cor: "var(--color-lime)",
    fundoCor: "var(--color-lime-d)",
  },
  {
    label: "Ver folha",
    descricao: "Holerites do mês.",
    href: "/pessoal",
    icon: Users,
    cor: "var(--color-blue)",
    fundoCor: "var(--color-blue-d)",
  },
  {
    label: "Ver fluxo de caixa",
    descricao: "Projeção 90 dias.",
    href: "/controles",
    icon: Wallet,
    cor: "var(--color-amber)",
    fundoCor: "var(--color-amber-d)",
  },
  {
    label: "Falar com o assistente",
    descricao: "Pergunte sobre seus impostos.",
    href: "/assistente",
    icon: Sparkles,
    cor: "var(--color-lime)",
    fundoCor: "var(--color-lime-d)",
  },
];

export function QuickActions() {
  return (
    <Card className="p-5 flex flex-col gap-3">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
        Atalhos
      </span>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {ATALHOS.map((a) => (
          <Link
            key={a.href}
            href={a.href}
            className="group rounded-md border p-3 transition-all hover:-translate-y-0.5 flex flex-col gap-2 bg-[var(--color-card-2)] border-[var(--color-line-2)] hover:bg-[var(--color-card-3)]"
          >
            <span
              className="size-8 rounded-md grid place-items-center"
              style={{ background: a.fundoCor }}
            >
              <a.icon className="size-4" style={{ color: a.cor }} />
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-bold text-[var(--color-txt)] flex items-center gap-1.5">
                {a.label}
                <ArrowRight className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
              </span>
              <span className="text-[11px] text-[var(--color-txt-2)] leading-snug">
                {a.descricao}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}
