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
          className="size-14 rounded-full grid place-items-center border"
          style={{
            borderColor: "var(--color-line-2)",
            background: "var(--color-card-2)",
          }}
        >
          <Icon className="size-6" style={{ color: "var(--color-txt-3)" }} />
        </div>
      ) : (
        <EmptyIllustration />
      )}
      <div className="flex flex-col gap-1.5 max-w-sm">
        <h3
          className="text-[15px] font-semibold"
          style={{ color: "var(--color-txt)" }}
        >
          {titulo}
        </h3>
        {descricao ? (
          <p className="text-sm" style={{ color: "var(--color-txt-2)" }}>
            {descricao}
          </p>
        ) : null}
      </div>
      {acao}
    </div>
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
      <defs>
        <linearGradient id="empty-paper" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-card-2)" />
          <stop offset="100%" stopColor="var(--color-card)" />
        </linearGradient>
      </defs>
      <rect
        x={20}
        y={16}
        width={48}
        height={62}
        rx={6}
        fill="url(#empty-paper)"
        stroke="var(--color-line-2)"
        strokeWidth={1.5}
      />
      <line
        x1={28}
        y1={32}
        x2={56}
        y2={32}
        stroke="var(--color-line-2)"
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <line
        x1={28}
        y1={42}
        x2={60}
        y2={42}
        stroke="var(--color-line-2)"
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <line
        x1={28}
        y1={52}
        x2={48}
        y2={52}
        stroke="var(--color-line-2)"
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <circle
        cx={66}
        cy={64}
        r={12}
        fill="var(--color-bg-2)"
        stroke="var(--color-lime)"
        strokeWidth={2}
      />
      <line
        x1={75}
        y1={73}
        x2={84}
        y2={82}
        stroke="var(--color-lime)"
        strokeWidth={2.5}
        strokeLinecap="round"
      />
    </svg>
  );
}
