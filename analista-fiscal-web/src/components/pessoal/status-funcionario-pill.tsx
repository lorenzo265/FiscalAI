import { Pill } from "@/components/shared/pill";
import {
  STATUS_FUNCIONARIO_LABEL,
  type StatusFuncionario,
} from "@/lib/schemas/pessoal";

const TONS = {
  ativo: "ok",
  afastado: "warn",
  demitido: "neutral",
} as const;

export function StatusFuncionarioPill({ status }: { status: StatusFuncionario }) {
  return <Pill tom={TONS[status]}>{STATUS_FUNCIONARIO_LABEL[status]}</Pill>;
}
