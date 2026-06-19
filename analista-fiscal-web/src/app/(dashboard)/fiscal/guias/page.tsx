"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Download, QrCode, Receipt } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Moeda } from "@/components/shared/moeda";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { PixModal } from "@/components/fiscal/pix-modal";
import { useFiscalGuias } from "@/hooks/use-fiscal-guias";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useCountUp } from "@/lib/motion/use-count-up";
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

  /* ── número-herói: próxima guia em aberto (resolve "quanto pagar agora?") ── */
  const proximaAberta = React.useMemo<GuiaDAS | null>(
    () => data?.find((g) => g.status !== "pago") ?? null,
    [data]
  );
  const heroValorCentavos = Math.round((proximaAberta?.valor ?? 0) * 100);
  const heroRaw = useCountUp(heroValorCentavos, {
    id: "guias:proxima",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

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

  /* ── colunas DataTable ── */
  const colunas = React.useMemo<DataTableColumn<GuiaDAS>[]>(
    () => [
      {
        id: "periodo",
        header: "Período",
        primary: true,
        cell: (g) => (
          <div className="flex flex-col min-w-0 gap-0.5">
            <span
              className="mono text-sm font-bold text-[var(--color-ink)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {g.rotulo}
            </span>
            <span
              className="mono text-[11px] text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {g.numeroDocumento}
            </span>
          </div>
        ),
        width: "11rem",
      },
      {
        id: "status",
        header: "Status",
        cell: (g) =>
          g.status === "pago" ? (
            <Carimbo tom="green" sub={g.pagaEm ? formatarDataBR(g.pagaEm) : undefined}>
              Pago
            </Carimbo>
          ) : (
            <StatusPill status={g.status} />
          ),
        width: "8rem",
      },
      {
        id: "receita",
        header: "Receita mês",
        mono: true,
        align: "right",
        cell: (g) => (
          <span
            className="mono text-sm text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarMoeda(g.faturamentoMes)}
          </span>
        ),
        width: "9rem",
      },
      {
        id: "valor",
        header: "Valor DAS",
        mono: true,
        align: "right",
        cell: (g) => (
          <span
            className="mono text-sm font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={g.valor} />
          </span>
        ),
        width: "8.5rem",
      },
      {
        id: "vencimento",
        header: "Vencimento",
        mono: true,
        cell: (g) => (
          <span
            className="mono text-xs text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {g.pagaEm
              ? `pago ${formatarDataBR(g.pagaEm)}`
              : formatarDataBR(g.vencimento)}
          </span>
        ),
        width: "8rem",
      },
      {
        id: "acoes",
        header: "",
        hideLabelOnCard: true,
        /* controles interativos: içados acima do stretched-link */
        interactive: true,
        cell: (g) => (
          <div className="flex items-center gap-1.5 justify-end">
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
        ),
        width: "8rem",
      },
    ],
    [baixarPdf, gerandoId]
  );

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── Bloco 1: cabeçalho + número-herói + ação primária ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-4"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemVariants}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Módulo · Fiscal
            </motion.span>
            <motion.h1
              variants={itemVariants}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Guias do DAS
            </motion.h1>
          </div>

          {/* Ação primária única — verde 44px */}
          {proximaAberta ? (
            <motion.div variants={itemVariants} className="shrink-0 pt-5 md:pt-6">
              <Button
                size="default"
                className="h-11 px-5 gap-2"
                onClick={() => setGuiaPix(proximaAberta)}
              >
                <QrCode className="size-4" aria-hidden />
                Pagar via PIX
              </Button>
            </motion.div>
          ) : null}
        </div>

        {/* número-herói: próxima guia em aberto */}
        {proximaAberta ? (
          <motion.div variants={itemVariants} className="flex flex-col gap-1">
            {isLoading ? (
              <>
                <Skeleton className="h-16 w-52" />
                <Skeleton className="h-4 w-40 mt-1" />
              </>
            ) : (
              <>
                <span
                  className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
                  style={{
                    fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                    fontWeight: 300,
                    fontVariantNumeric: "tabular-nums",
                    letterSpacing: "-0.02em",
                  }}
                  aria-label={`Próxima guia a pagar: ${heroFormatado}`}
                >
                  {heroFormatado}
                </span>
                <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
                  guia de{" "}
                  <span className="text-[var(--color-ink)]">{proximaAberta.rotulo}</span>
                  {" · vence em "}
                  <span
                    className="mono font-semibold text-[var(--color-ink)]"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {formatarDataBR(proximaAberta.vencimento)}
                  </span>
                </span>
              </>
            )}
          </motion.div>
        ) : data && data.length > 0 ? (
          /* todas as guias pagas — state resolvido */
          <motion.div variants={itemVariants} className="flex items-center gap-3 pt-1">
            <Carimbo tom="green">Em dia</Carimbo>
            <span className="text-sm text-[var(--color-ink-2)]">
              Todas as guias do período estão quitadas.
            </span>
          </motion.div>
        ) : null}
      </motion.header>

      <FiscalSubnav />

      {/* ── Bloco 2: lista de guias ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando guias..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma guia ainda"
          descricao="Quando sua apuração for fechada, ela aparece aqui."
          icone={Receipt}
        />
      ) : (
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
          {/* label de seção Hanken — sem Fig. */}
          <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Histórico de guias
            </h2>
          </div>

          {/* DataTable: tabela no md+, card no mobile */}
          <DataTable<GuiaDAS>
            data={data}
            columns={colunas}
            getRowKey={(g) => g.id}
            getRowLabel={(g) => `Guia DAS ${g.rotulo}`}
            caption="Histórico de guias DAS"
          />
        </Framed>
      )}

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
