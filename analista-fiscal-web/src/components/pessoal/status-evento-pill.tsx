import { Pill } from "@/components/shared/pill";
import type { StatusEventoEsocial } from "@/lib/schemas/pessoal";

const TONS = {
  transmitido: "ok",
  pendente: "warn",
  erro: "error",
  rascunho: "neutral",
} as const;

const LABEL = {
  transmitido: "transmitido",
  pendente: "pendente",
  erro: "erro",
  rascunho: "rascunho",
};

export function StatusEventoPill({ status }: { status: StatusEventoEsocial }) {
  return <Pill tom={TONS[status]}>{LABEL[status]}</Pill>;
}
