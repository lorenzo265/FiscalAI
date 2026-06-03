import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  titulo: string;
  descricao?: string;
  icone?: LucideIcon;
  acao?: React.ReactNode;
  className?: string;
};

export function EmptyState({
  titulo,
  descricao,
  icone: Icon,
  acao,
  className,
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-16 px-6 text-center",
        className
      )}
    >
      {Icon ? (
        <div
          className="relative size-14 rounded-[var(--radius-md)] grid place-items-center border"
          style={{
            borderColor: "var(--color-ink)",
            background: "var(--color-paper)",
          }}
        >
          <Icon className="size-6" style={{ color: "var(--color-ink-2)" }} />
          <CornerTicks />
        </div>
      ) : (
        <EmptyIllustration />
      )}
      <div className="flex flex-col gap-1.5 max-w-sm">
        <h3
          className="font-[family-name:var(--font-serif)] text-lg font-semibold leading-tight"
          style={{ color: "var(--color-ink)" }}
        >
          {titulo}
        </h3>
        {descricao ? (
          <p className="text-sm" style={{ color: "var(--color-ink-2)" }}>
            {descricao}
          </p>
        ) : null}
      </div>
      {acao}
    </div>
  );
}

/** Marcas de mira nos cantos do ícone — reforço da linguagem técnica. */
function CornerTicks() {
  const c = "var(--color-rule-2)";
  const base: React.CSSProperties = {
    position: "absolute",
    width: 5,
    height: 5,
    borderStyle: "solid",
    borderColor: c,
  };
  return (
    <span aria-hidden className="pointer-events-none absolute inset-0">
      <span style={{ ...base, top: -3, left: -3, borderWidth: "1px 0 0 1px" }} />
      <span style={{ ...base, top: -3, right: -3, borderWidth: "1px 1px 0 0" }} />
      <span style={{ ...base, bottom: -3, left: -3, borderWidth: "0 0 1px 1px" }} />
      <span style={{ ...base, bottom: -3, right: -3, borderWidth: "0 1px 1px 0" }} />
    </span>
  );
}

function EmptyIllustration() {
  return (
    <svg
      width={96}
      height={96}
      viewBox="0 0 96 96"
      fill="none"
      role="presentation"
      aria-hidden="true"
    >
      <rect
        x={20}
        y={16}
        width={48}
        height={62}
        rx={2}
        fill="var(--color-paper)"
        stroke="var(--color-graphite)"
        strokeWidth={1.25}
      />
      <line
        x1={28}
        y1={32}
        x2={56}
        y2={32}
        stroke="var(--color-graphite)"
        strokeWidth={1.25}
        strokeLinecap="round"
      />
      <line
        x1={28}
        y1={42}
        x2={60}
        y2={42}
        stroke="var(--color-graphite)"
        strokeWidth={1.25}
        strokeLinecap="round"
      />
      <line
        x1={28}
        y1={52}
        x2={48}
        y2={52}
        stroke="var(--color-graphite)"
        strokeWidth={1.25}
        strokeLinecap="round"
      />
      <circle
        cx={66}
        cy={64}
        r={12}
        fill="var(--color-paper)"
        stroke="var(--color-green)"
        strokeWidth={1.75}
      />
      <line
        x1={75}
        y1={73}
        x2={84}
        y2={82}
        stroke="var(--color-green)"
        strokeWidth={2}
        strokeLinecap="round"
      />
    </svg>
  );
}
