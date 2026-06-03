"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, FileLock2, ShieldCheck, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
import { Carimbo } from "@/components/blueprint/carimbo";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { cn } from "@/lib/utils";

export function PassoCertificado() {
  const certificadoNome = useOnboardingStore((s) => s.certificadoNome);
  const certificadoSenha = useOnboardingStore((s) => s.certificadoSenha);
  const pulado = useOnboardingStore((s) => s.certificadoPulado);
  const setCertificado = useOnboardingStore((s) => s.setCertificado);
  const marcarPulado = useOnboardingStore((s) => s.marcarCertificadoPulado);
  const proximo = useOnboardingStore((s) => s.proximo);
  const voltar = useOnboardingStore((s) => s.voltar);
  const dados = useOnboardingStore((s) => s.dadosReceita);

  const [fileName, setFileName] = React.useState<string | null>(certificadoNome);
  const [senha, setSenha] = React.useState<string>(certificadoSenha ?? "");
  const [arrastando, setArrastando] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  function handleFile(file: File | null) {
    if (!file) return;
    setFileName(file.name);
  }

  function confirmar() {
    if (!fileName) return;
    setCertificado(fileName, senha);
    proximo();
  }

  function pular() {
    marcarPulado();
    proximo();
  }

  const validade = "08/05/2027";
  const subjectMock = dados?.razaoSocial ?? "Arkan Demo Ltda";
  const certificadoCompleto = !!fileName;

  return (
    <div className="flex flex-col gap-5">
      {/* dropzone com crop marks no hover */}
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          const f = e.dataTransfer.files[0];
          handleFile(f ?? null);
        }}
        className={cn(
          "flex flex-col items-center gap-3 p-8 rounded-[var(--radius-md)] border-2 border-dashed transition-colors text-left w-full",
          arrastando
            ? "border-[var(--color-green)] bg-[var(--color-green-wash)]"
            : "border-[var(--color-rule-2)] bg-[var(--color-paper-2)] hover:bg-[var(--color-rule)]"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pfx,.p12"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
        <div
          className="size-12 rounded-[var(--radius-sm)] grid place-items-center border"
          style={{
            background: "var(--color-green-wash)",
            borderColor: "var(--color-green)",
          }}
        >
          <Upload className="size-5" style={{ color: "var(--color-green)" }} />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-[var(--color-ink)]">
            {fileName
              ? fileName
              : "Arraste o certificado aqui ou clique para selecionar"}
          </p>
          <p className="text-xs text-[var(--color-ink-3)] mt-1 mono">
            Aceitamos arquivos .pfx ou .p12 (certificado A1).
          </p>
        </div>
      </button>

      {/* senha */}
      {fileName ? (
        <div className="flex flex-col gap-1.5">
          <Label
            htmlFor="senha-cert"
            className="text-[11px] mono uppercase tracking-[0.12em] font-bold text-[var(--color-ink-3)]"
          >
            Senha do certificado
          </Label>
          <Input
            id="senha-cert"
            type="password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </div>
      ) : null}

      {/* confirmação com Carimbo */}
      {certificadoCompleto ? (
        <div
          className="rounded-[var(--radius-md)] border p-4 flex items-start gap-3"
          style={{
            background: "var(--color-green-wash)",
            borderColor: "var(--color-green)",
          }}
        >
          <ShieldCheck
            className="size-5 mt-0.5 shrink-0"
            style={{ color: "var(--color-green)" }}
          />
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold text-[var(--color-ink)]">
                Certificado carregado
              </span>
              <Pill tom="ok">A1</Pill>
            </div>
            <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
              {subjectMock} · válido até{" "}
              <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
                {validade}
              </span>
            </p>
          </div>
          <Carimbo tom="green" sub="válido">A1</Carimbo>
        </div>
      ) : null}

      {/* nota de segurança */}
      <div
        className="rounded-[var(--radius-md)] border p-3 flex items-start gap-2.5"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule-2)",
        }}
      >
        <FileLock2
          className="size-4 mt-0.5 shrink-0"
          style={{ color: "var(--color-ink-2)" }}
        />
        <p className="text-xs text-[var(--color-ink-2)] leading-relaxed">
          Sem certificado, você continua usando relatórios e o assistente. A
          emissão de NF-e fica indisponível — pode pular agora e adicionar
          depois em Configurações.
        </p>
      </div>

      <div className="flex items-center justify-between pt-2">
        <Button variant="ghost" onClick={pular} className="text-xs text-[var(--color-ink-3)]">
          {pulado ? "Pulando..." : "Pular por enquanto"}
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={voltar}>
            <ArrowLeft className="size-4" /> Voltar
          </Button>
          <Button onClick={confirmar} disabled={!certificadoCompleto}>
            Continuar <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
