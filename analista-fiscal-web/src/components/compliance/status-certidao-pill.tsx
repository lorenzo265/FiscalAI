import { CheckCircle2, AlertTriangle, XCircle, Clock } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import type { StatusCertidao } from "@/lib/schemas/compliance";

const CFG: Record<
  StatusCertidao,
  { tom: "ok" | "warn" | "error"; label: string; Icon: typeof CheckCircle2 }
> = {
  vigente:       { tom: "ok",   label: "vigente",        Icon: CheckCircle2  },
  vence_em_breve:{ tom: "warn", label: "vence em breve", Icon: Clock         },
  vencida:       { tom: "error",label: "vencida",        Icon: XCircle       },
  irregular:     { tom: "error",label: "irregular",      Icon: AlertTriangle },
};

export function StatusCertidaoPill({ status }: { status: StatusCertidao }) {
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
