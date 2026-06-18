import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Circle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type PillTom = "ok" | "warn" | "error" | "info" | "neutral";

/**
 * Pill — etiqueta de status na linguagem Arkan. Apesar do nome herdado, NÃO é
 * mais um "pílula" arredondada: é uma etiqueta técnica de cantos quase-retos
 * (radius 2px), mono caixa-alta. Status = **cor + ícone + palavra** (invariante
 * do plano §7) — o ícone vem por padrão e pode ser desligado com `semIcone`.
 * Único acento cromático é o verde (`ok`); warn/error/info ficam no mundo
 * quente (ocre/danger) ou neutro, nunca um 2º acento de marca.
 */
const tons: Record<PillTom, { cls: string; icon: LucideIcon }> = {
  ok: {
    cls: "bg-[var(--color-green-wash)] text-[var(--color-green-deep)] border-[var(--color-green)]/30",
    icon: CheckCircle2,
  },
  warn: {
    cls: "bg-[var(--color-ochre-wash)] text-[var(--color-ochre)] border-[var(--color-ochre)]/35",
    icon: AlertTriangle,
  },
  error: {
    cls: "bg-[var(--color-danger-wash)] text-[var(--color-danger)] border-[var(--color-danger)]/35",
    icon: XCircle,
  },
  info: {
    cls: "bg-[var(--color-paper-2)] text-[var(--color-ink-2)] border-[var(--color-rule-2)]",
    icon: Info,
  },
  neutral: {
    cls: "bg-[var(--color-paper-2)] text-[var(--color-ink-2)] border-[var(--color-rule-2)]",
    icon: Circle,
  },
};

type Props = {
  tom: PillTom;
  children: React.ReactNode;
  className?: string;
  /** Esconde o ícone (use só quando o contexto já comunica o status). */
  semIcone?: boolean;
};

export function Pill({ tom, children, className, semIcone = false }: Props) {
  const { cls, icon: Icon } = tons[tom];
  return (
    <span
      className={cn(
        "mono inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-[var(--radius-sm)] tracking-[0.12em] font-bold uppercase border whitespace-nowrap",
        cls,
        className
      )}
    >
      {!semIcone ? <Icon className="size-3 shrink-0" aria-hidden /> : null}
      {children}
    </span>
  );
}
