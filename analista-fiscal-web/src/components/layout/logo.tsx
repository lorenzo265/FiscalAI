import { cn } from "@/lib/utils";

type Props = {
  size?: number;
  className?: string;
};

/**
 * Logo — selo do Arkan. Não é um app-icon lavado: é uma marca de registro
 * técnica (quadrado de fios 1px) com um losango verde de tinta no centro —
 * o "ponto de saúde fiscal" da marca. Usa só tokens canônicos (sem hardcode).
 */
export function Logo({ size = 28, className }: Props) {
  return (
    <span
      aria-hidden="true"
      className={cn("relative grid place-items-center shrink-0", className)}
      style={{
        width: size,
        height: size,
        border: "1px solid var(--color-ink)",
        borderRadius: "var(--radius-sm)",
        background: "var(--color-card)",
      }}
    >
      <svg
        viewBox="0 0 24 24"
        width={size * 0.62}
        height={size * 0.62}
        fill="none"
        stroke="var(--color-ink)"
        strokeWidth={1.6}
        strokeLinejoin="round"
      >
        {/* losango (diamante) — silhueta do "A" de Arkan / ponto de medição */}
        <path d="M12 3 L20 12 L12 21 L4 12 Z" />
        {/* miolo verde de tinta — o acento da marca */}
        <path d="M12 8 L16 12 L12 16 L8 12 Z" fill="var(--color-green)" stroke="none" />
      </svg>
    </span>
  );
}
