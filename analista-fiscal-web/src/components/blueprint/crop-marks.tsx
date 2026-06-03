import { cn } from "@/lib/utils";

/**
 * CropMarks — marcas de registro técnico nos quatro cantos de um painel.
 * São dois fios 1px por canto (L invertido), em `--color-rule-2`/`--color-ink`,
 * posicionados FORA da borda como nas provas de impressão. Decorativo.
 *
 * Use solto dentro de um container `relative` ou via `<Framed marks>`.
 */
type Props = {
  /** Comprimento de cada braço da marca (px). */
  size?: number;
  /** Distância da marca para fora do canto (px). */
  offset?: number;
  className?: string;
  /** Marca mais escura (tinta) em vez de fio claro. */
  ink?: boolean;
};

export function CropMarks({ size = 7, offset = 4, className, ink = false }: Props) {
  const color = ink ? "var(--color-ink)" : "var(--color-rule-2)";
  const corners = [
    { top: -offset, left: -offset, bw: "1px 0 0 1px" },
    { top: -offset, right: -offset, bw: "1px 1px 0 0" },
    { bottom: -offset, left: -offset, bw: "0 0 1px 1px" },
    { bottom: -offset, right: -offset, bw: "0 1px 1px 0" },
  ] as const;

  return (
    <span
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0", className)}
    >
      {corners.map((c, i) => (
        <span
          key={i}
          style={{
            position: "absolute",
            width: size,
            height: size,
            borderStyle: "solid",
            borderColor: color,
            borderWidth: c.bw,
            top: "top" in c ? c.top : undefined,
            bottom: "bottom" in c ? c.bottom : undefined,
            left: "left" in c ? c.left : undefined,
            right: "right" in c ? c.right : undefined,
          }}
        />
      ))}
    </span>
  );
}
