"use client";

import * as React from "react";
import { Download, FileText, QrCode } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { PixModal } from "@/components/fiscal/pix-modal";
import { useFiscalGuias } from "@/hooks/use-fiscal-guias";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { formatarDataBR } from "@/lib/format/data";
import { formatarMoeda } from "@/lib/format/moeda";
import type { GuiaDAS } from "@/lib/schemas/guias";

export default function FiscalGuiasPage() {
  const { empresa } = useEmpresaAtual();
  const { data, isLoading, isError, refetch } = useFiscalGuias();
  const [guiaPix, setGuiaPix] = React.useState<GuiaDAS | null>(null);
  const [gerandoId, setGerandoId] = React.useState<string | null>(null);

  const baixarPdf = React.useCallback(
    async (guia: GuiaDAS) => {
      if (!empresa) return;
      setGerandoId(guia.id);
      try {
        const { gerarPdfDAS, nomeArquivoDAS } = await import("@/lib/pdf/das");
        const doc = gerarPdfDAS({
          empresa: { razaoSocial: empresa.razaoSocial, cnpj: empresa.cnpj },
          periodo: guia.periodo,
          faturamentoMes: guia.faturamentoMes,
          aliquotaEfetiva: guia.aliquotaEfetiva,
          valorDAS: guia.valor,
          vencimento: guia.vencimento,
          codigoBarras: guia.codigoBarras,
          numeroDocumento: guia.numeroDocumento,
        });
        doc.save(nomeArquivoDAS(guia.periodo));
        toast.success("Guia baixada", {
          description: `DAS de ${guia.rotulo} salvo em PDF.`,
        });
      } catch (err) {
        console.error(err);
        toast.error("Falha ao gerar PDF", {
          description: "Tente novamente em instantes.",
        });
      } finally {
        setGerandoId(null);
      }
    },
    [empresa]
  );

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo fiscal
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Guias do DAS
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Baixe o PDF, copie o PIX, conferencie o que já foi pago.
        </p>
      </header>

      <FiscalSubnav />

      {isLoading ? (
        <LoadingState titulo="Carregando guias..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma guia ainda"
          descricao="Quando sua apuração for fechada, ela aparece aqui."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="grid grid-cols-[1fr_auto] md:grid-cols-[120px_1fr_140px_140px_120px_auto] gap-3 px-5 py-3 border-b text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono"
            style={{ borderColor: "var(--color-line)" }}
          >
            <span className="hidden md:block">Período</span>
            <span>Documento</span>
            <span className="hidden md:block text-right">Receita mês</span>
            <span className="hidden md:block text-right">Valor</span>
            <span className="hidden md:block">Vencimento</span>
            <span className="text-right">Ações</span>
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
            {data.map((g) => (
              <li
                key={g.id}
                className="grid grid-cols-[1fr_auto] md:grid-cols-[120px_1fr_140px_140px_120px_auto] gap-3 px-5 py-3.5 items-center hover:bg-[var(--color-card-2)] transition-colors"
                style={{ borderColor: "var(--color-line)" }}
              >
                <span className="hidden md:block mono text-sm font-bold text-[var(--color-txt)]">
                  {g.rotulo}
                </span>

                <div className="flex flex-col gap-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <FileText className="size-3.5 text-[var(--color-txt-3)] shrink-0" />
                    <span className="mono text-xs text-[var(--color-txt-2)] truncate">
                      {g.numeroDocumento}
                    </span>
                    <StatusPill status={g.status} />
                  </div>
                  <span className="md:hidden text-[11px] text-[var(--color-txt-3)]">
                    {g.rotulo} · vence {formatarDataBR(g.vencimento)}
                  </span>
                </div>

                <span className="hidden md:block mono text-sm text-[var(--color-txt-2)] text-right">
                  {formatarMoeda(g.faturamentoMes)}
                </span>
                <span className="hidden md:block mono text-sm font-bold text-[var(--color-txt)] text-right">
                  <Moeda valor={g.valor} />
                </span>
                <span className="hidden md:block mono text-xs text-[var(--color-txt-2)]">
                  {g.pagaEm
                    ? `pago ${formatarDataBR(g.pagaEm)}`
                    : formatarDataBR(g.vencimento)}
                </span>

                <div className="flex items-center gap-1.5 justify-end col-span-2 md:col-span-1">
                  <span className="md:hidden mono text-sm font-bold text-[var(--color-txt)] mr-1">
                    <Moeda valor={g.valor} />
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void baixarPdf(g)}
                    disabled={gerandoId === g.id}
                  >
                    <Download className="size-3.5" />
                    <span className="hidden sm:inline">PDF</span>
                  </Button>
                  {g.status !== "pago" ? (
                    <Button size="sm" onClick={() => setGuiaPix(g)}>
                      <QrCode className="size-3.5" />
                      <span className="hidden sm:inline">PIX</span>
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {isLoading ? <Skeleton className="h-24 w-full" /> : null}

      {guiaPix ? (
        <PixModal
          aberto={!!guiaPix}
          onAbertoChange={(v) => !v && setGuiaPix(null)}
          valor={guiaPix.valor}
          vencimento={guiaPix.vencimento}
          pixCopiaCola={guiaPix.pixCopiaCola}
          rotuloPeriodo={guiaPix.rotulo}
        />
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: GuiaDAS["status"] }) {
  const map: Record<GuiaDAS["status"], { tom: PillTom; texto: string }> = {
    em_aberto: { tom: "info", texto: "em aberto" },
    pago: { tom: "ok", texto: "pago" },
    atrasado: { tom: "error", texto: "atrasado" },
  };
  const { tom, texto } = map[status];
  return <Pill tom={tom}>{texto}</Pill>;
}
