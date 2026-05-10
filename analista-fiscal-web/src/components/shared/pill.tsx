import { cn } from "@/lib/utils";

export type PillTom = "ok" | "warn" | "error" | "info" | "neutral";

const tons: Record<PillTom, string> = {
  ok: "bg-[var(--color-lime-d)] text-[var(--color-lime)] border-[rgba(163,255,107,0.22)]",
  warn: "bg-[var(--color-amber-d)] text-[var(--color-amber)] border-[rgba(255,184,77,0.22)]",
  error: "bg-[var(--color-red-d)] text-[var(--color-red)] border-[rgba(255,85,102,0.22)]",
  info: "bg-[var(--color-blue-d)] text-[var(--color-blue)] border-[rgba(77,142,255,0.22)]",
  neutral: "bg-[var(--color-card-2)] text-[var(--color-txt-2)] border-[var(--color-line-2)]",
};

type Props = {
  tom: PillTom;
  children: React.ReactNode;
  className?: string;
};

export function Pill({ tom, children, className }: Props) {
  return (
    <span
      className={cn(
        "mono inline-flex items-center text-[9px] px-2 py-0.5 rounded-full tracking-[0.12em] font-bold uppercase border whitespace-nowrap",
        tons[tom],
        className
      )}
    >
      {children}
    </span>
  );
}
