import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  titulo?: string;
  descricao?: string;
  onTentarNovamente?: () => void;
  className?: string;
};

export function ErrorState({
  titulo = "Algo deu errado",
  descricao = "Não conseguimos carregar essa informação agora.",
  onTentarNovamente,
  className,
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16 px-6 text-center",
        className
      )}
    >
      <div
        className="size-12 rounded-[var(--radius-md)] grid place-items-center border"
        style={{
          borderColor: "var(--color-danger)",
          background: "var(--color-paper)",
        }}
      >
        <AlertTriangle className="size-5" style={{ color: "var(--color-danger)" }} />
      </div>
      <h3
        className="font-[family-name:var(--font-serif)] text-lg font-semibold leading-tight"
        style={{ color: "var(--color-ink)" }}
      >
        {titulo}
      </h3>
      <p className="text-sm max-w-sm" style={{ color: "var(--color-ink-2)" }}>
        {descricao}
      </p>
      {onTentarNovamente ? (
        <button
          type="button"
          onClick={onTentarNovamente}
          className="mono mt-2 text-[11px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-[var(--radius-sm)] border transition-colors hover:bg-[var(--color-paper-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/35"
          style={{
            color: "var(--color-ink)",
            borderColor: "var(--color-ink)",
            background: "transparent",
          }}
        >
          Tentar de novo
        </button>
      ) : null}
    </div>
  );
}
