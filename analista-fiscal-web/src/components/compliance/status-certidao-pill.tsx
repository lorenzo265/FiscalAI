import { Pill } from "@/components/shared/pill";
import type { StatusCertidao } from "@/lib/schemas/compliance";

const TONS = {
  vigente: "ok",
  vence_em_breve: "warn",
  vencida: "error",
  irregular: "error",
} as const;

const LABEL = {
  vigente: "vigente",
  vence_em_breve: "vence em breve",
  vencida: "vencida",
  irregular: "irregular",
};

export function StatusCertidaoPill({ status }: { status: StatusCertidao }) {
  return <Pill tom={TONS[status]}>{LABEL[status]}</Pill>;
}
