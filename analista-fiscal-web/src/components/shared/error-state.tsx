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
        className="size-12 rounded-full grid place-items-center border"
        style={{
          borderColor: "rgba(255, 85, 102, 0.22)",
          background: "var(--color-red-d)",
        }}
      >
        <AlertTriangle className="size-5" style={{ color: "var(--color-red)" }} />
      </div>
      <h3 className="text-[15px] font-semibold" style={{ color: "var(--color-txt)" }}>
        {titulo}
      </h3>
      <p className="text-sm max-w-sm" style={{ color: "var(--color-txt-2)" }}>
        {descricao}
      </p>
      {onTentarNovamente ? (
        <button
          type="button"
          onClick={onTentarNovamente}
          className="mono mt-2 text-[11px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-md border transition-colors"
          style={{
            color: "var(--color-txt)",
            borderColor: "var(--color-line-2)",
            background: "var(--color-card-2)",
          }}
        >
          Tentar de novo
        </button>
      ) : null}
    </div>
  );
}
