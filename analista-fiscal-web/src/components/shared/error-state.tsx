import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { traduzirErro, ERRO_GENERICO, type EntradaErro } from "@/lib/traducao/erros";

type Props = {
  /**
   * Código de erro do backend (ex.: "CnpjInvalido") ou HTTP (ex.: "http_404").
   * Se não informado, usa o fallback genérico.
   */
  codigoErro?: string;
  /**
   * Substitui o texto "o que se passou" — útil quando o chamador já tem
   * a frase pronta. Se informado, `codigoErro` é ignorado.
   */
  titulo?: string;
  /**
   * Substitui o texto "o que fazer". Só usado quando `titulo` é fornecido.
   */
  descricao?: string;
  /** Chamado ao clicar em "Tentar de novo" — sobrepõe o botão de rota. */
  onTentarNovamente?: () => void;
  className?: string;
};

export function ErrorState({
  codigoErro,
  titulo,
  descricao,
  onTentarNovamente,
  className,
}: Props) {
  // Resolve o texto: props explícitas > mapa de erros > fallback genérico
  let entrada: EntradaErro;
  if (titulo) {
    entrada = {
      oqueSePasso: titulo,
      oqueFazer: descricao ?? ERRO_GENERICO.oqueFazer,
      rotuloBotao: onTentarNovamente ? "Tentar de novo" : undefined,
    };
  } else if (codigoErro) {
    entrada = traduzirErro(codigoErro);
  } else {
    entrada = ERRO_GENERICO;
  }

  const { oqueSePasso, oqueFazer, rotuloBotao, rotaAcao } = entrada;

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16 px-6 text-center",
        className
      )}
    >
      {/* ícone em moldura técnica 2px — sem fundo lavado genérico */}
      <div
        className="size-12 rounded-[var(--radius-md)] grid place-items-center border"
        style={{
          borderColor: "var(--color-danger)",
          background: "var(--color-paper)",
        }}
      >
        <AlertTriangle className="size-5" style={{ color: "var(--color-danger)" }} />
      </div>

      {/* o que houve */}
      <h3
        className="font-[family-name:var(--font-serif)] text-lg font-semibold leading-tight"
        style={{ color: "var(--color-ink)" }}
      >
        {oqueSePasso}
      </h3>

      {/* o que fazer */}
      <p className="text-sm max-w-sm leading-relaxed" style={{ color: "var(--color-ink-2)" }}>
        {oqueFazer}
      </p>

      {/* ação: callback tem prioridade sobre rota */}
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
          {rotuloBotao ?? "Tentar de novo"}
        </button>
      ) : rotaAcao ? (
        <Link
          href={rotaAcao}
          className="mono mt-2 text-[11px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-[var(--radius-sm)] border transition-colors hover:bg-[var(--color-paper-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/35 inline-flex items-center"
          style={{
            color: "var(--color-ink)",
            borderColor: "var(--color-ink)",
            background: "transparent",
          }}
        >
          {rotuloBotao ?? "Ir"}
        </Link>
      ) : rotuloBotao ? (
        /* Botão sem ação específica — só visual, sem ação */
        <span
          className="mono mt-2 text-[11px] font-bold uppercase tracking-[0.14em] px-3 py-1.5 rounded-[var(--radius-sm)] border"
          style={{
            color: "var(--color-ink-3)",
            borderColor: "var(--color-rule)",
            background: "transparent",
          }}
        >
          {rotuloBotao}
        </span>
      ) : null}
    </div>
  );
}
