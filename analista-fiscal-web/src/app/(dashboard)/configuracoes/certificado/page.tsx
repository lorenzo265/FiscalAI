"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, FileLock2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { SubstituirCertificadoModal } from "@/components/configuracoes/substituir-certificado-modal";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { formatarDataBR } from "@/lib/format/data";

export default function ConfiguracoesCertificadoPage() {
  const { empresa, loading } = useEmpresaAtual();
  const [modalAberto, setModalAberto] = React.useState(false);

  const certificado = empresa?.certificadoA1;
  const diasParaVencer = certificado
    ? Math.ceil(
        (new Date(certificado.validade).getTime() - Date.now()) /
          (24 * 60 * 60 * 1000)
      )
    : null;

  const tom = !certificado
    ? "warn"
    : diasParaVencer != null && diasParaVencer < 30
      ? "warn"
      : "ok";

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link
          href="/configuracoes"
          className="text-[11px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-txt-2)] transition-colors"
        >
          <ArrowLeft className="size-3" />
          Configurações
        </Link>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)] mt-1">
          Certificado digital A1
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          O A1 é o que assina e autoriza a emissão das suas notas. Sem ele, a
          NF-e não sai. Mantenha sempre um vigente.
        </p>
      </header>

      <ConfiguracoesSubnav />

      {loading ? (
        <LoadingState titulo="Carregando dados do certificado..." />
      ) : !certificado ? (
        <>
          <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <ShieldAlert className="size-4 mt-0.5 shrink-0" />
              <div>
                <AlertTitle>Sem certificado A1 instalado</AlertTitle>
                <AlertDescription>
                  Você não consegue emitir NF-e até instalar um. Use seu e-CPF
                  ou e-CNPJ.
                </AlertDescription>
              </div>
            </div>
            <Button onClick={() => setModalAberto(true)} className="shrink-0">
              <FileLock2 className="size-4" /> Instalar certificado
            </Button>
          </Alert>

          <Card className="p-5 flex items-start gap-3 text-sm text-[var(--color-txt-2)]">
            <FileLock2 className="size-4 text-[var(--color-blue)] mt-0.5" />
            <p className="leading-relaxed">
              Aceitamos arquivos <span className="mono">.pfx</span> ou{" "}
              <span className="mono">.p12</span>. O certificado fica salvo
              criptografado neste navegador — nada é enviado para servidores
              externos durante esta demonstração.
            </p>
          </Card>
        </>
      ) : (
        <>
          <Card className="p-6 flex flex-col gap-5">
            <div className="flex items-start gap-4">
              <div
                className="size-12 rounded-md grid place-items-center"
                style={{ background: "var(--color-lime-d)" }}
              >
                <ShieldCheck className="size-5 text-[var(--color-lime)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-[var(--color-txt)] truncate">
                    {certificado.nomeArquivo}
                  </span>
                  <Pill tom={tom}>{tom === "ok" ? "vigente" : "atenção"}</Pill>
                </div>
                <p className="text-xs text-[var(--color-txt-2)] mt-1">
                  Emitido para{" "}
                  <span className="text-[var(--color-txt)] font-semibold">
                    {empresa?.razaoSocial}
                  </span>
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <Info label="Validade">
                <span className="mono text-sm text-[var(--color-txt)] font-semibold">
                  {formatarDataBR(certificado.validade)}
                </span>
              </Info>
              <Info label="Expira em">
                <span className="mono text-sm text-[var(--color-txt)] font-semibold">
                  {diasParaVencer != null && diasParaVencer >= 0
                    ? `${diasParaVencer} dia${diasParaVencer === 1 ? "" : "s"}`
                    : "Vencido"}
                </span>
              </Info>
              <Info label="Tipo">
                <span className="mono text-sm text-[var(--color-txt)] font-semibold">
                  A1 — arquivo
                </span>
              </Info>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t" style={{ borderColor: "var(--color-line)" }}>
              <p className="text-xs text-[var(--color-txt-3)] max-w-md">
                Vai expirar em menos de 30 dias? Substitua agora para não
                interromper a emissão de notas.
              </p>
              <Button onClick={() => setModalAberto(true)}>
                <RefreshCw className="size-4" />
                Substituir certificado
              </Button>
            </div>
          </Card>
        </>
      )}

      {empresa ? (
        <SubstituirCertificadoModal
          open={modalAberto}
          onOpenChange={setModalAberto}
          empresa={empresa}
        />
      ) : null}
    </div>
  );
}

function Info({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)]">
        {label}
      </span>
      {children}
    </div>
  );
}
