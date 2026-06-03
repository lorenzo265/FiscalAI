import * as React from "react";
import { AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import type { StatusContaPagarReceber } from "@/lib/schemas/controles";

const CONFIG: Record<
  StatusContaPagarReceber,
  { tom: "ok" | "warn" | "error" | "neutral"; texto: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  pendente: { tom: "warn", texto: "pendente", Icon: Clock },
  pago: { tom: "ok", texto: "pago", Icon: CheckCircle2 },
  atrasado: { tom: "error", texto: "atrasado", Icon: AlertCircle },
};

export function StatusContaPill({ status }: { status: StatusContaPagarReceber }) {
  const { tom, texto, Icon } = CONFIG[status];
  return (
    <Pill tom={tom}>
      <Icon className="size-3 inline-block mr-0.5" />
      {texto}
    </Pill>
  );
}
