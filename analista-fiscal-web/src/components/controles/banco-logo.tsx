import { cn } from "@/lib/utils";

interface Props {
  cor: string;
  textoCor: string;
  iniciais: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const TAMANHOS = {
  sm: "size-8 text-[10px]",
  md: "size-10 text-xs",
  lg: "size-12 text-sm",
};

export function BancoLogo({ cor, textoCor, iniciais, size = "md", className }: Props) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-sm)] grid place-items-center font-bold mono shrink-0",
        TAMANHOS[size],
        className
      )}
      style={{ background: cor, color: textoCor }}
      aria-hidden
    >
      {iniciais}
    </div>
  );
}
