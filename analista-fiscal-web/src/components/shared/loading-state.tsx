import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  titulo?: string;
  className?: string;
};

export function LoadingState({ titulo = "Carregando...", className }: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16 px-6 text-center",
        className
      )}
    >
      <Loader2
        className="size-5 animate-spin"
        style={{ color: "var(--color-green)" }}
      />
      <span className="mono text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--color-ink-2)" }}>
        {titulo}
      </span>
    </div>
  );
}
