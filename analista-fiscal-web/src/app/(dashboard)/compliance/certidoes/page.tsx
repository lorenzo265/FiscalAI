"use client";

import * as React from "react";
import {
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { ComplianceSubnav } from "@/components/compliance/compliance-subnav";
import { StatusCertidaoPill } from "@/components/compliance/status-certidao-pill";
import {
  useCertidoes,
  useRenovarCertidao,
} from "@/hooks/use-compliance";
import { formatarDataBR } from "@/lib/format/data";
import {
  TIPO_CERTIDAO_DESCRICAO,
  TIPO_CERTIDAO_LABEL,
  type Certidao,
} from "@/lib/schemas/compliance";

export default function CertidoesPage() {
  const { data, isLoading, isError, refetch } = useCertidoes();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Compliance · Certidões
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Certidões negativas
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          São o atestado de que a empresa está em dia com tributos federais,
          FGTS e justiça do trabalho. A gente vigia o vencimento e renova com
          1 clique.
        </p>
      </header>

      <ComplianceSubnav />

      {isLoading ? (
        <LoadingState titulo="Verificando certidões..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <Card className="p-8 text-center text-sm text-[var(--color-txt-2)]">
          Nenhuma certidão emitida ainda.
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {data.map((c) => (
            <CardCertidao key={c.id} certidao={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function CardCertidao({ certidao }: { certidao: Certidao }) {
  const renovar = useRenovarCertidao();
  const dias = Math.ceil(
    (new Date(certidao.vencimento).getTime() - Date.now()) /
      (24 * 60 * 60 * 1000)
  );

  const renovando = renovar.isPending && renovar.variables === certidao.id;

  return (
    <Card className="p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-[var(--color-lime)]" />
          <span className="text-sm font-bold text-[var(--color-txt)]">
            {TIPO_CERTIDAO_LABEL[certidao.tipo]}
          </span>
        </div>
        <StatusCertidaoPill status={certidao.status} />
      </div>

      <p className="text-xs text-[var(--color-txt-2)] line-clamp-3">
        {TIPO_CERTIDAO_DESCRICAO[certidao.tipo]}
      </p>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
            Emitida em
          </span>
          <p className="mono text-sm font-semibold text-[var(--color-txt)]">
            {formatarDataBR(certidao.emitidaEm)}
          </p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
            Vencimento
          </span>
          <p className="mono text-sm font-semibold text-[var(--color-txt)]">
            {formatarDataBR(certidao.vencimento)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px] mono">
        <Clock className="size-3 text-[var(--color-txt-3)]" />
        <span
          className={
            certidao.status === "vence_em_breve"
              ? "text-[var(--color-amber)]"
              : certidao.status === "vencida"
                ? "text-[var(--color-red)]"
                : "text-[var(--color-txt-3)]"
          }
        >
          {certidao.status === "vencida"
            ? `Vencida há ${Math.abs(dias)} dia${Math.abs(dias) === 1 ? "" : "s"}`
            : dias <= 0
              ? "Vence hoje"
              : `Vence em ${dias} dia${dias === 1 ? "" : "s"}`}
        </span>
      </div>

      <div className="text-[10px] mono text-[var(--color-txt-3)] truncate">
        Nº {certidao.numero} · {certidao.emitidaPor}
      </div>

      <Button
        onClick={async () => {
          const renovada = await renovar.mutateAsync(certidao.id);
          if (renovada) {
            toast.success(
              `${TIPO_CERTIDAO_LABEL[renovada.tipo]} renovada`,
              {
                description: `Nova validade até ${formatarDataBR(renovada.vencimento)}.`,
              }
            );
          }
        }}
        disabled={renovando}
        variant={
          certidao.status === "vence_em_breve" || certidao.status === "vencida"
            ? "default"
            : "outline"
        }
        className="self-start"
      >
        {renovando ? (
          <Loader2 className="size-4 animate-spin" />
        ) : certidao.status === "vigente" ? (
          <CheckCircle2 className="size-4" />
        ) : (
          <RefreshCw className="size-4" />
        )}
        {certidao.status === "vigente" ? "Re-emitir" : "Renovar agora"}
      </Button>

      {renovar.isPending && renovar.variables === certidao.id ? (
        <Pill tom="info">Conectando ao órgão emissor...</Pill>
      ) : null}
    </Card>
  );
}
