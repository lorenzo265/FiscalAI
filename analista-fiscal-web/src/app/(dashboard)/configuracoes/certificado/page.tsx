"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, FileLock2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { LoadingState } from "@/components/shared/loading-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { Carimbo } from "@/components/blueprint/carimbo";
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
          className="text-[11px] mono uppercase tracking-[0.12em] text-[var(--color-ink-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-ink-2)] transition-colors"
        >
          <ArrowLeft className="size-3" />
          Configurações
        </Link>
        <h1 className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight mt-1">
          Certificado digital A1
        </h1>
        <p className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1">
          O certificado A1 assina e autoriza a emissão das notas fiscais. Sem
          ele, a NF-e não é emitida. Mantenha sempre um vigente.
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
                  A emissão de NF-e está indisponível. Instale um certificado
                  e-CPF ou e-CNPJ para continuar.
                </AlertDescription>
              </div>
            </div>
            <Button onClick={() => setModalAberto(true)} className="shrink-0">
              <FileLock2 className="size-4" /> Instalar certificado
            </Button>
          </Alert>

          <Framed marks={false} tone="rule" surface="paper-2" className="flex items-start gap-3">
            <FileLock2 className="size-4 text-[var(--color-ink-2)] mt-0.5 shrink-0" />
            <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
              Aceitamos arquivos <code className="mono text-[var(--color-ink)]">.pfx</code> ou{" "}
              <code className="mono text-[var(--color-ink)]">.p12</code>. O certificado fica salvo
              criptografado neste navegador — nada é enviado para servidores
              externos nesta demonstração.
            </p>
          </Framed>
        </>
      ) : (
        <Framed marks tone="rule" surface="card" padded={false}>
          {/* Fig. 01 — Certificado instalado */}
          <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-2">
            <Fig n={1} titulo="Certificado instalado" size="sm" />
          </div>
          <Ruler />

          <div className="px-5 py-5 flex flex-col gap-5">
            <div className="flex items-start gap-4">
              <div
                className="size-12 rounded-[var(--radius-sm)] grid place-items-center shrink-0"
                style={{ background: "var(--color-green-wash)" }}
              >
                <ShieldCheck
                  className="size-5"
                  style={{ color: "var(--color-green)" }}
                />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold text-[var(--color-ink)] truncate mono">
                    {certificado.nomeArquivo}
                  </span>
                  <Pill tom={tom}>
                    {tom === "ok" ? "vigente" : "atenção"}
                  </Pill>
                </div>
                <p className="text-xs text-[var(--color-ink-2)] mt-1">
                  Emitido para{" "}
                  <span className="text-[var(--color-ink)] font-semibold">
                    {empresa?.razaoSocial}
                  </span>
                </p>
              </div>
              {/* Carimbo para certificado vigente */}
              {tom === "ok" ? (
                <Carimbo tom="green" sub="válido">A1</Carimbo>
              ) : null}
            </div>

            {/* dados em mono tabular */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <InfoCampo label="Validade">
                <span className="mono text-sm text-[var(--color-ink)] font-semibold"
                      style={{ fontVariantNumeric: "tabular-nums" }}>
                  {formatarDataBR(certificado.validade)}
                </span>
              </InfoCampo>
              <InfoCampo label="Expira em">
                <span
                  className="mono text-sm font-semibold"
                  style={{
                    color:
                      diasParaVencer == null || diasParaVencer < 0
                        ? "var(--color-danger)"
                        : diasParaVencer < 30
                          ? "var(--color-ochre)"
                          : "var(--color-ink)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {diasParaVencer != null && diasParaVencer >= 0
                    ? `${diasParaVencer} dia${diasParaVencer === 1 ? "" : "s"}`
                    : "Vencido"}
                </span>
              </InfoCampo>
              <InfoCampo label="Tipo">
                <span className="mono text-sm text-[var(--color-ink)] font-semibold">
                  A1 — arquivo
                </span>
              </InfoCampo>
            </div>

            <div
              className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t"
              style={{ borderColor: "var(--color-rule)" }}
            >
              <p className="text-xs text-[var(--color-ink-3)] max-w-md">
                Expirando em menos de 30 dias? Substitua agora para não
                interromper a emissão de notas.
              </p>
              <Button onClick={() => setModalAberto(true)}>
                <RefreshCw className="size-4" />
                Substituir certificado
              </Button>
            </div>
          </div>
        </Framed>
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

function InfoCampo({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)]">
        {label}
      </span>
      {children}
    </div>
  );
}
