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
        style={{ color: "var(--color-lime)" }}
      />
      <span className="text-sm" style={{ color: "var(--color-txt-2)" }}>
        {titulo}
      </span>
    </div>
  );
}
