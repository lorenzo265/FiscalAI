import { Pill, type PillTom } from "@/components/shared/pill";
import type { StatusManifesto, StatusNota } from "@/lib/schemas/nota";

const MAP_STATUS: Record<StatusNota, { tom: PillTom; texto: string }> = {
  rascunho: { tom: "neutral", texto: "rascunho" },
  emitida: { tom: "info", texto: "em processamento" },
  autorizada: { tom: "ok", texto: "autorizada" },
  rejeitada: { tom: "error", texto: "rejeitada" },
  cancelada: { tom: "warn", texto: "cancelada" },
  denegada: { tom: "error", texto: "denegada" },
};

export function StatusNotaPill({ status }: { status: StatusNota }) {
  const cfg = MAP_STATUS[status];
  return <Pill tom={cfg.tom}>{cfg.texto}</Pill>;
}

const MAP_MANIFESTO: Record<StatusManifesto, { tom: PillTom; texto: string }> = {
  pendente_manifesto: { tom: "warn", texto: "pendente" },
  ciencia: { tom: "info", texto: "ciência" },
  confirmada: { tom: "ok", texto: "confirmada" },
  desconhecida: { tom: "neutral", texto: "desconhecida" },
  nao_realizada: { tom: "error", texto: "não realizada" },
};

export function ManifestoPill({ manifesto }: { manifesto: StatusManifesto }) {
  const cfg = MAP_MANIFESTO[manifesto];
  return <Pill tom={cfg.tom}>{cfg.texto}</Pill>;
}

export function TipoNotaPill({ tipo }: { tipo: "entrada" | "saida" }) {
  return (
    <Pill tom={tipo === "saida" ? "ok" : "info"}>
      {tipo === "saida" ? "saída" : "entrada"}
    </Pill>
  );
}
