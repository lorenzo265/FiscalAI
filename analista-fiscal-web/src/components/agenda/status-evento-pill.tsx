import { Pill } from "@/components/shared/pill";
import type { EventoAgenda } from "@/lib/schemas/agenda";

const TONS = {
  pago: "ok",
  pendente: "warn",
  atrasado: "error",
  informativo: "info",
} as const;

const LABEL = {
  pago: "pago",
  pendente: "pendente",
  atrasado: "atrasado",
  informativo: "info",
};

export function StatusEventoAgendaPill({
  status,
}: {
  status: EventoAgenda["status"];
}) {
  return <Pill tom={TONS[status]}>{LABEL[status]}</Pill>;
}

export const COR_STATUS_AGENDA: Record<EventoAgenda["status"], string> = {
  pago: "var(--color-lime)",
  pendente: "var(--color-amber)",
  atrasado: "var(--color-red)",
  informativo: "var(--color-blue)",
};
