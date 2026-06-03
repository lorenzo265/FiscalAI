"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Download, FileText, QrCode } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { PixModal } from "@/components/fiscal/pix-modal";
import { useFiscalGuias } from "@/hooks/use-fiscal-guias";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { formatarDataBR } from "@/lib/format/data";
import { formatarMoeda } from "@/lib/format/moeda";
import type { GuiaDAS } from "@/lib/schemas/guias";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function FiscalGuiasPage() {
  const { empresa } = useEmpresaAtual();
  const { data, isLoading, isError, refetch } = useFiscalGuias();
  const [guiaPix, setGuiaPix] = React.useState<GuiaDAS | null>(null);
  const [gerandoId, setGerandoId] = React.useState<string | null>(null);
  const reduced = useReducedMotion();

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

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
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Fiscal
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Guias do DAS
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Baixe o PDF, copie o PIX, confira o que já foi pago.
        </motion.p>
      </motion.header>

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
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          {/* cabeçalho tabela */}
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo="Registro de guias DAS" size="sm" />
          </div>
          <Ruler />
          <div
            className="grid grid-cols-[1fr_auto] md:grid-cols-[120px_1fr_140px_140px_120px_auto] gap-3 px-5 py-3 text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono"
          >
            <span className="hidden md:block">Período</span>
            <span>Documento</span>
            <span className="hidden md:block text-right">Receita mês</span>
            <span className="hidden md:block text-right">Valor</span>
            <span className="hidden md:block">Vencimento</span>
            <span className="text-right">Ações</span>
          </div>
          <Ruler />
          <ul>
            {data.map((g) => (
              <li
                key={g.id}
                className="grid grid-cols-[1fr_auto] md:grid-cols-[120px_1fr_140px_140px_120px_auto] gap-3 px-5 py-3.5 items-center border-b last:border-b-0 hover:bg-[var(--color-paper-2)] transition-colors"
                style={{ borderColor: "var(--color-rule)" }}
              >
                <span
                  className="hidden md:block mono text-sm font-bold text-[var(--color-ink)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {g.rotulo}
                </span>

                <div className="flex flex-col gap-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <FileText className="size-3.5 text-[var(--color-ink-3)] shrink-0" aria-hidden />
                    <span
                      className="mono text-xs text-[var(--color-ink-2)] truncate"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {g.numeroDocumento}
                    </span>
                    <StatusPill status={g.status} />
                  </div>
                  <span className="md:hidden text-[11px] text-[var(--color-ink-3)]">
                    {g.rotulo} · vence {formatarDataBR(g.vencimento)}
                  </span>
                </div>

                <span
                  className="hidden md:block mono text-sm text-[var(--color-ink-2)] text-right"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {formatarMoeda(g.faturamentoMes)}
                </span>
                <span
                  className="hidden md:block mono text-sm font-bold text-[var(--color-ink)] text-right"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  <Moeda valor={g.valor} />
                </span>
                <span
                  className="hidden md:block mono text-xs text-[var(--color-ink-2)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {g.pagaEm
                    ? `pago ${formatarDataBR(g.pagaEm)}`
                    : formatarDataBR(g.vencimento)}
                </span>

                <div className="flex items-center gap-1.5 justify-end col-span-2 md:col-span-1">
                  <span
                    className="md:hidden mono text-sm font-bold text-[var(--color-ink)] mr-1"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
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
        </Framed>
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
    </motion.div>
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
