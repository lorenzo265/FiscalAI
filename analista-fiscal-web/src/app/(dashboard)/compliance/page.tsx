"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  FileWarning,
  Mail,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { Framed } from "@/components/blueprint/framed";
import { Carimbo } from "@/components/blueprint/carimbo";
import { ComplianceSubnav } from "@/components/compliance/compliance-subnav";
import {
  useCertidoes,
  useCompliancePainel,
} from "@/hooks/use-compliance";
import { formatarDataBR } from "@/lib/format/data";
import {
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

export default function CompliancePage() {
  const {
    data: painel,
    isLoading,
    isError,
    refetch,
  } = useCompliancePainel();
  const { data: certidoes } = useCertidoes();
  const reduced = useReducedMotion();

  if (isLoading) return <LoadingState titulo="Verificando compliance..." />;
  if (isError || !painel)
    return <ErrorState onTentarNovamente={() => void refetch()} />;

  const certidoesProximas = (certidoes ?? [])
    .filter((c) => c.status === "vence_em_breve")
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));

  const tudoEmDia =
    painel.certidoesVigentes === painel.certidoesTotal &&
    painel.intimacoesAbertas === 0 &&
    painel.parcelamentosAtivos === 0;

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
          Compliance · Painel
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Situação fiscal da empresa
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          Quatro pontos definem se a empresa está apta a emitir nota,
          participar de licitação ou contratar com o governo: certidões,
          intimações, parcelamentos e CNPJ.
        </motion.p>
      </motion.header>

      <ComplianceSubnav />

      {/* ── banner de status ── */}
      {tudoEmDia ? (
        <Alert variant="ok" className="flex items-start gap-3">
          <CheckCircle2 className="size-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <AlertTitle>Tudo em dia</AlertTitle>
            <AlertDescription>
              Empresa habilitada a emitir NF, contratar com o governo e
              renovar contratos.
            </AlertDescription>
          </div>
          {/* Carimbo — signature do estado resolvido */}
          <Carimbo tom="green" sub="em dia">regular</Carimbo>
        </Alert>
      ) : certidoesProximas.length > 0 ? (
        <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0" />
            <div>
              <AlertTitle>
                {certidoesProximas.length} certidão
                {certidoesProximas.length > 1 ? "ões" : ""} vence
                {certidoesProximas.length > 1 ? "m" : ""} em breve
              </AlertTitle>
              <AlertDescription>
                Renove agora — sem CND atualizada você não consegue emitir
                NF-e nem participar de licitação.
              </AlertDescription>
            </div>
          </div>
          <Button asChild className="shrink-0">
            <Link href="/compliance/certidoes">
              Renovar certidões <ArrowRight className="size-4" />
            </Link>
          </Button>
        </Alert>
      ) : null}

      {/* ── Indicadores ── */}
      <Framed marks={false} tone="rule" surface="card" padded={false}>
        <div className="px-5 pt-4 pb-2 border-b" style={{ borderColor: "var(--color-rule)" }}>
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
            Indicadores de conformidade
          </h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x" style={{ borderColor: "var(--color-rule)" }}>
          <CardPainel
            icone={ShieldCheck}
            rotulo="Certidões"
            titulo={`${painel.certidoesVigentes}/${painel.certidoesTotal} vigentes`}
            tom={painel.certidoesVigentes === painel.certidoesTotal ? "ok" : "warn"}
            descricao={
              painel.proximaCertidaoVencimento
                ? `Próxima: ${formatarDataBR(painel.proximaCertidaoVencimento)}`
                : "Sem vencimentos próximos"
            }
            href="/compliance/certidoes"
          />
          <CardPainel
            icone={Mail}
            rotulo="Intimações"
            titulo={
              painel.intimacoesAbertas > 0
                ? `${painel.intimacoesAbertas} aberta${painel.intimacoesAbertas > 1 ? "s" : ""}`
                : "Nenhuma aberta"
            }
            tom={painel.intimacoesAbertas > 0 ? "warn" : "ok"}
            descricao={`${painel.intimacoesTotal} no histórico`}
            href="/compliance/intimacoes"
          />
          <CardPainel
            icone={FileWarning}
            rotulo="Parcelamentos"
            titulo={
              painel.parcelamentosAtivos === 0
                ? "Sem parcelamentos"
                : `${painel.parcelamentosAtivos} ativo${painel.parcelamentosAtivos > 1 ? "s" : ""}`
            }
            tom={painel.parcelamentosAtivos === 0 ? "ok" : "warn"}
            descricao="Refis, PERSE e similares"
            href="/compliance/parcelamentos"
          />
          <CardPainel
            icone={Building2}
            rotulo="CNPJ"
            titulo={painel.cnpjAtivo ? "Ativo" : "Suspenso"}
            tom={painel.cnpjAtivo ? "ok" : "error"}
            descricao="Verificação automática a cada 7 dias"
          />
        </div>
      </Framed>

      {/* ── certidões a renovar ── */}
      {certidoesProximas.length > 0 ? (
        <Framed marks={false} tone="rule" surface="card" padded={false}>
          <div className="px-5 pt-4 pb-2 border-b flex items-center justify-between gap-2" style={{ borderColor: "var(--color-rule)" }}>
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Certidões a renovar
            </h2>
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
            {certidoesProximas.map((c) => (
              <LinhaCertidaoResumo key={c.id} certidao={c} />
            ))}
          </ul>
        </Framed>
      ) : null}
    </motion.div>
  );
}

function CardPainel({
  icone: Icon,
  rotulo,
  titulo,
  tom,
  descricao,
  href,
}: {
  icone: typeof ShieldCheck;
  rotulo: string;
  titulo: string;
  tom: "ok" | "warn" | "error";
  descricao: string;
  href?: string;
}) {
  const corIcone =
    tom === "ok"
      ? "var(--color-green)"
      : tom === "warn"
        ? "var(--color-ochre)"
        : "var(--color-danger)";

  const StatusIcon =
    tom === "ok" ? CheckCircle2 : tom === "warn" ? AlertTriangle : XCircle;

  const conteudo = (
    <div className="p-4 flex flex-col gap-2 h-full hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-ink-3)]">
          {rotulo}
        </span>
        <Icon className="size-4" style={{ color: corIcone }} />
      </div>
      <p className="mono text-sm font-bold text-[var(--color-ink)] leading-tight"
         style={{ fontVariantNumeric: "tabular-nums" }}>
        {titulo}
      </p>
      <p className="text-xs text-[var(--color-ink-2)] line-clamp-2">
        {descricao}
      </p>
      <Pill tom={tom}>
        <span className="flex items-center gap-1">
          <StatusIcon className="size-3" />
          {tom === "ok" ? "regular" : tom === "warn" ? "atenção" : "crítico"}
        </span>
      </Pill>
      {href ? (
        <span className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-green)] mt-auto">
          Ver detalhes →
        </span>
      ) : null}
    </div>
  );

  if (!href) return conteudo;
  return (
    <Link href={href} className="block">
      {conteudo}
    </Link>
  );
}

function LinhaCertidaoResumo({ certidao }: { certidao: Certidao }) {
  const dias = Math.ceil(
    (new Date(certidao.vencimento).getTime() - Date.now()) /
      (24 * 60 * 60 * 1000)
  );
  return (
    <li className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[var(--color-ink)] truncate">
          {TIPO_CERTIDAO_LABEL[certidao.tipo]}
        </p>
        <p className="text-[11px] text-[var(--color-ink-2)] mono"
           style={{ fontVariantNumeric: "tabular-nums" }}>
          Vence em {formatarDataBR(certidao.vencimento)} · {dias} dia{dias === 1 ? "" : "s"}
        </p>
      </div>
      <Button asChild variant="outline" size="sm">
        <Link href="/compliance/certidoes">Renovar</Link>
      </Button>
    </li>
  );
}
