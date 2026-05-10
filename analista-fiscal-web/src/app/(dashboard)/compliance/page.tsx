"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  FileWarning,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
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

export default function CompliancePage() {
  const {
    data: painel,
    isLoading,
    isError,
    refetch,
  } = useCompliancePainel();
  const { data: certidoes } = useCertidoes();

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

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Compliance · Painel
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Como está sua situação fiscal
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Quatro pontos definem se a empresa está apta pra emitir nota,
          participar de licitação ou contratar com o governo: certidões,
          intimações, parcelamentos e CNPJ.
        </p>
      </header>

      <ComplianceSubnav />

      {tudoEmDia ? (
        <Alert variant="ok" className="flex items-start gap-3">
          <CheckCircle2 className="size-4 mt-0.5" />
          <div>
            <AlertTitle>Tudo em dia</AlertTitle>
            <AlertDescription>
              Empresa habilitada a emitir NF, contratar com o governo e
              renovar contratos. Mantemos monitorando os prazos pra você.
            </AlertDescription>
          </div>
        </Alert>
      ) : certidoesProximas.length > 0 ? (
        <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0" />
            <div>
              <AlertTitle>
                {certidoesProximas.length} certidão{certidoesProximas.length > 1 ? "ões" : ""} vence{certidoesProximas.length > 1 ? "m" : ""} em breve
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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <CardPainel
          icone={ShieldCheck}
          rotulo="Certidões"
          titulo={`${painel.certidoesVigentes} de ${painel.certidoesTotal} vigentes`}
          tom={
            painel.certidoesVigentes === painel.certidoesTotal
              ? "ok"
              : "warn"
          }
          descricao={
            painel.proximaCertidaoVencimento
              ? `Próxima vence em ${formatarDataBR(painel.proximaCertidaoVencimento)}`
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
          descricao={`${painel.intimacoesTotal} no histórico total`}
          href="/compliance/intimacoes"
        />
        <CardPainel
          icone={FileWarning}
          rotulo="Parcelamentos"
          titulo={
            painel.parcelamentosAtivos === 0
              ? "Sem débitos parcelados"
              : `${painel.parcelamentosAtivos} ativo${painel.parcelamentosAtivos > 1 ? "s" : ""}`
          }
          tom={painel.parcelamentosAtivos === 0 ? "ok" : "warn"}
          descricao="Histórico limpo no Refis e PERSE"
          href="/compliance/parcelamentos"
        />
        <CardPainel
          icone={Building2}
          rotulo="CNPJ"
          titulo={painel.cnpjAtivo ? "Ativo" : "Suspenso"}
          tom={painel.cnpjAtivo ? "ok" : "error"}
          descricao="Última verificação automática há 5h"
        />
      </div>

      {certidoesProximas.length > 0 ? (
        <Card className="p-5 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Certidões a renovar
            </span>
          </div>
          <ul
            className="divide-y -mx-2"
            style={{ borderColor: "var(--color-line)" }}
          >
            {certidoesProximas.map((c) => (
              <LinhaCertidaoResumo key={c.id} certidao={c} />
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
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
      ? "var(--color-lime)"
      : tom === "warn"
        ? "var(--color-amber)"
        : "var(--color-red)";

  const conteudo = (
    <Card interactive={!!href} className="p-4 flex flex-col gap-2 h-full">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
          {rotulo}
        </span>
        <Icon className="size-4" style={{ color: corIcone }} />
      </div>
      <p className="text-sm font-bold text-[var(--color-txt)] leading-tight">
        {titulo}
      </p>
      <p className="text-xs text-[var(--color-txt-2)] line-clamp-2">
        {descricao}
      </p>
      <Pill tom={tom}>{tom === "ok" ? "ok" : tom === "warn" ? "atenção" : "crítico"}</Pill>
    </Card>
  );

  if (!href) return conteudo;
  return (
    <Link
      href={href}
      className="block hover:[&>div]:border-[var(--color-line-2)] transition-colors"
    >
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
    <li className="px-2 py-2.5 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[var(--color-txt)] truncate">
          {TIPO_CERTIDAO_LABEL[certidao.tipo]}
        </p>
        <p className="text-[11px] text-[var(--color-txt-3)] mono">
          Vence em {formatarDataBR(certidao.vencimento)} · {dias} dia{dias === 1 ? "" : "s"}
        </p>
      </div>
      <Button asChild variant="outline">
        <Link href="/compliance/certidoes">Renovar</Link>
      </Button>
    </li>
  );
}
