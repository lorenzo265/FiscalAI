"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
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
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function CertidoesPage() {
  const { data, isLoading, isError, refetch } = useCertidoes();
  const reduced = useReducedMotion();

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header variants={containerVariants} initial="hidden" animate="show">
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Compliance · Certidões
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Certidões negativas
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          Atestam que a empresa está em dia com tributos federais, FGTS e
          justiça do trabalho. Monitoramos o vencimento e renovamos com um
          clique.
        </motion.p>
      </motion.header>

      <ComplianceSubnav />

      {isLoading ? (
        <LoadingState titulo="Verificando certidões..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma certidão emitida"
          descricao="As certidões serão listadas aqui conforme forem solicitadas."
          icone={ShieldCheck}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {data.map((c) => (
            <CardCertidao key={c.id} certidao={c} />
          ))}
        </div>
      )}
    </motion.div>
  );
}

function CardCertidao({ certidao }: { certidao: Certidao }) {
  const renovar = useRenovarCertidao();
  const dias = Math.ceil(
    (new Date(certidao.vencimento).getTime() - Date.now()) /
      (24 * 60 * 60 * 1000)
  );

  const renovando = renovar.isPending && renovar.variables === certidao.id;
  const ehVigente = certidao.status === "vigente";

  return (
    <Framed marks={false} tone="rule" surface="card" padded={false} className="flex flex-col">
      {/* cabeçalho */}
      <div className="px-5 pt-4 pb-2 border-b flex items-start justify-between gap-2" style={{ borderColor: "var(--color-rule)" }}>
        <div className="flex items-center gap-2">
          <ShieldCheck
            className="size-4 shrink-0"
            style={{ color: "var(--color-green)" }}
          />
          <span className="text-sm font-bold text-[var(--color-ink)]">
            {TIPO_CERTIDAO_LABEL[certidao.tipo]}
          </span>
        </div>
        <StatusCertidaoPill status={certidao.status} />
      </div>

      <div className="px-5 py-4 flex flex-col gap-4 flex-1">
        <p className="text-xs text-[var(--color-ink-2)] leading-relaxed line-clamp-3">
          {TIPO_CERTIDAO_DESCRICAO[certidao.tipo]}
        </p>

        {/* datas em mono tabular */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]">
              Emitida em
            </span>
            <span className="mono text-sm font-semibold text-[var(--color-ink)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatarDataBR(certidao.emitidaEm)}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]">
              Vencimento
            </span>
            <span className="mono text-sm font-semibold text-[var(--color-ink)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatarDataBR(certidao.vencimento)}
            </span>
          </div>
        </div>

        {/* contagem de dias */}
        <div className="flex items-center gap-2 text-[11px] mono">
          <Clock className="size-3 text-[var(--color-ink-3)]" />
          <span
            style={{
              color:
                certidao.status === "vence_em_breve"
                  ? "var(--color-ochre)"
                  : certidao.status === "vencida"
                    ? "var(--color-danger)"
                    : "var(--color-ink-2)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {certidao.status === "vencida"
              ? `Vencida há ${Math.abs(dias)} dia${Math.abs(dias) === 1 ? "" : "s"}`
              : dias <= 0
                ? "Vence hoje"
                : `Vence em ${dias} dia${dias === 1 ? "" : "s"}`}
          </span>
        </div>

        {/* número e emissor */}
        <div className="text-[10px] mono text-[var(--color-ink-2)] truncate">
          <abbr title="Número do protocolo/certidão">Nº</abbr> {certidao.numero} · {certidao.emitidaPor}
        </div>

        {/* ações */}
        <div className="flex items-center justify-between gap-2 mt-auto">
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
            size="sm"
          >
            {renovando ? (
              <Loader2 className="size-4 animate-spin" />
            ) : ehVigente ? (
              <CheckCircle2 className="size-4" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            {ehVigente ? "Re-emitir" : "Renovar agora"}
          </Button>

          {/* Carimbo para estado vigente */}
          {ehVigente && !renovando ? (
            <Carimbo tom="green" sub="vigente" inView>regular</Carimbo>
          ) : null}
        </div>

        {renovando ? (
          <Pill tom="info">Conectando ao órgão emissor...</Pill>
        ) : null}
      </div>
    </Framed>
  );
}
