import { Pill } from "@/components/shared/pill";
import type { StatusContaPagarReceber } from "@/lib/schemas/controles";

const TONS = {
  pendente: "warn",
  pago: "ok",
  atrasado: "error",
} as const;

const LABEL = {
  pendente: "pendente",
  pago: "pago",
  atrasado: "atrasado",
};

export function StatusContaPill({ status }: { status: StatusContaPagarReceber }) {
  return <Pill tom={TONS[status]}>{LABEL[status]}</Pill>;
}
