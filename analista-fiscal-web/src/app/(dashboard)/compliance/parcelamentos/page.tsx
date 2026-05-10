"use client";

import { CheckCircle2, FileWarning } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { ComplianceSubnav } from "@/components/compliance/compliance-subnav";
import { useParcelamentos } from "@/hooks/use-compliance";
import {
  ORGAO_LABEL,
  type Parcelamento,
} from "@/lib/schemas/compliance";
import { formatarDataBR } from "@/lib/format/data";

export default function ParcelamentosPage() {
  const { data, isLoading, isError, refetch } = useParcelamentos();

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Compliance · Parcelamentos
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Parcelamentos fiscais
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Refis, PERSE, PRT e outros programas de parcelamento. A gente
          acompanha as parcelas pra você não cair em rescisão.
        </p>
      </header>

      <ComplianceSubnav />

      {isLoading ? (
        <LoadingState titulo="Verificando parcelamentos..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhum débito parcelado"
          descricao="Sua situação está limpa. A empresa não está em nenhum programa de parcelamento — Refis, PERSE, PRT ou similar."
          icone={CheckCircle2}
        />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
            {data.map((p) => (
              <LinhaParcelamento key={p.id} parcelamento={p} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function LinhaParcelamento({
  parcelamento,
}: {
  parcelamento: Parcelamento;
}) {
  const progresso =
    (parcelamento.parcelaAtual / parcelamento.totalParcelas) * 100;
  return (
    <li className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <FileWarning className="size-4 text-[var(--color-amber)]" />
          <span className="text-sm font-bold text-[var(--color-txt)]">
            {parcelamento.assunto}
          </span>
        </div>
        <p className="text-[11px] mono text-[var(--color-txt-3)] mt-1">
          {ORGAO_LABEL[parcelamento.orgao]} · Nº {parcelamento.numero}
        </p>
        <div className="mt-2 flex items-center gap-2 text-xs">
          <div
            className="flex-1 h-1.5 rounded-full overflow-hidden"
            style={{ background: "var(--color-card-3)" }}
          >
            <div
              className="h-full"
              style={{
                background: "var(--color-amber)",
                width: `${progresso}%`,
              }}
            />
          </div>
          <span className="mono text-[var(--color-txt-2)]">
            {parcelamento.parcelaAtual}/{parcelamento.totalParcelas}
          </span>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        <Pill
          tom={parcelamento.status === "ativo" ? "warn" : "ok"}
        >
          {parcelamento.status}
        </Pill>
        <span className="mono text-base font-bold text-[var(--color-txt)]">
          <Moeda valor={parcelamento.saldoDevedor} />
        </span>
        <span className="text-[11px] text-[var(--color-txt-3)] mono">
          Próxima {formatarDataBR(parcelamento.proximoVencimento)}
        </span>
      </div>
    </li>
  );
}
