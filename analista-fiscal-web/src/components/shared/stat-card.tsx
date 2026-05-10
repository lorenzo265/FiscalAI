import { cn } from "@/lib/utils";
import type { PillTom } from "./pill";
import { Pill } from "./pill";

type Props = {
  label: string;
  valor: string | React.ReactNode;
  tom?: PillTom;
  sub?: React.ReactNode;
  pill?: { tom: PillTom; texto: string };
  className?: string;
};

export function StatCard({ label, valor, sub, pill, className }: Props) {
  return (
    <div
      className={cn(
        "rounded-[10px] border bg-[var(--color-card)] border-[var(--color-line)] p-4 flex flex-col gap-2",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
          {label}
        </span>
        {pill ? <Pill tom={pill.tom}>{pill.texto}</Pill> : null}
      </div>
      <div className="mono text-2xl font-semibold text-[var(--color-txt)] leading-tight">
        {valor}
      </div>
      {sub ? (
        <div className="text-xs text-[var(--color-txt-2)]">{sub}</div>
      ) : null}
    </div>
  );
}
