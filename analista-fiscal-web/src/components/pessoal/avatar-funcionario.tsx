import { cn } from "@/lib/utils";

const PALETA = [
  { bg: "rgba(163,255,107,0.18)", fg: "var(--color-lime)" },
  { bg: "rgba(77,142,255,0.18)", fg: "var(--color-blue)" },
  { bg: "rgba(255,184,77,0.18)", fg: "var(--color-amber)" },
  { bg: "rgba(255,85,102,0.18)", fg: "var(--color-red)" },
  { bg: "rgba(168,140,255,0.18)", fg: "#a88cff" },
  { bg: "rgba(255,140,200,0.18)", fg: "#ff8cc8" },
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
  const cor =
    PALETA[hash(seed) % PALETA.length] ?? PALETA[0]!;

  return (
    <div
      className={cn(
        "rounded-full grid place-items-center font-bold shrink-0 select-none",
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
