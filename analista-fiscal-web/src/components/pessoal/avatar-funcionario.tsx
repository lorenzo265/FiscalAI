import { cn } from "@/lib/utils";

/**
 * Avatar de funcionário: iniciais sobre fundo colorido derivado do seed.
 * Paleta usa tokens canônicos Arkan — sem hardcodes cromáticos externos.
 */
const PALETA = [
  { bg: "var(--color-green-wash)", fg: "var(--color-green)" },
  { bg: "var(--color-paper-2)", fg: "var(--color-ink-2)" },
  { bg: "var(--color-paper-2)", fg: "var(--color-ochre)" },
  { bg: "var(--color-paper-2)", fg: "var(--color-danger)" },
  { bg: "var(--color-paper-2)", fg: "var(--color-ink)" },
  { bg: "var(--color-green-wash)", fg: "var(--color-green-deep)" },
];

interface Props {
  nome: string;
  seed: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const TAMANHOS = {
  sm: "size-7 text-[10px]",
  md: "size-9 text-xs",
  lg: "size-12 text-sm",
};

export function AvatarFuncionario({ nome, seed, size = "md", className }: Props) {
  const iniciais = pegarIniciais(nome);
  const cor = PALETA[hash(seed) % PALETA.length] ?? PALETA[0]!;

  return (
    <div
      className={cn(
        "rounded-[var(--radius-sm)] grid place-items-center font-bold shrink-0 select-none mono",
        TAMANHOS[size],
        className
      )}
      style={{ background: cor.bg, color: cor.fg }}
      aria-hidden
    >
      {iniciais}
    </div>
  );
}

function pegarIniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0]!.slice(0, 2).toUpperCase();
  return `${partes[0]![0] ?? ""}${partes[partes.length - 1]![0] ?? ""}`.toUpperCase();
}

function hash(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) >>> 0;
  }
  return h;
}
