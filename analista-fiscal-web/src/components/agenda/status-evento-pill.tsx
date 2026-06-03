import { CheckCircle2, Clock, AlertTriangle, Info } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import type { EventoAgenda } from "@/lib/schemas/agenda";

const CFG: Record<
  EventoAgenda["status"],
  { tom: "ok" | "warn" | "error" | "info"; label: string; Icon: typeof CheckCircle2 }
> = {
  pago:        { tom: "ok",    label: "pago",       Icon: CheckCircle2 },
  pendente:    { tom: "warn",  label: "pendente",   Icon: Clock        },
  atrasado:    { tom: "error", label: "atrasado",   Icon: AlertTriangle},
  informativo: { tom: "info",  label: "informativo",Icon: Info         },
};

export function StatusEventoAgendaPill({
  status,
}: {
  status: EventoAgenda["status"];
}) {
  const { tom, label, Icon } = CFG[status];
  return (
    <Pill tom={tom}>
      <span className="flex items-center gap-1">
        <Icon className="size-3" />
        {label}
      </span>
    </Pill>
  );
}

export const COR_STATUS_AGENDA: Record<EventoAgenda["status"], string> = {
  pago:        "var(--color-green)",
  pendente:    "var(--color-ochre)",
  atrasado:    "var(--color-danger)",
  informativo: "var(--color-ink-2)",
};
