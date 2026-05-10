import { Pill, type PillTom } from "@/components/shared/pill";
import type { OrigemLancamento } from "@/lib/schemas/contabil";

const MAP: Record<OrigemLancamento, { tom: PillTom; texto: string }> = {
  nf_saida: { tom: "ok", texto: "NF saída" },
  nf_entrada: { tom: "info", texto: "NF entrada" },
  bancario: { tom: "warn", texto: "bancário" },
  folha: { tom: "info", texto: "folha" },
  manual: { tom: "neutral", texto: "manual" },
  fiscal: { tom: "warn", texto: "fiscal" },
  encerramento: { tom: "neutral", texto: "encerramento" },
};

export function OrigemPill({ origem }: { origem: OrigemLancamento }) {
  const cfg = MAP[origem];
  return <Pill tom={cfg.tom}>{cfg.texto}</Pill>;
}
