"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, FileLock2, ShieldCheck, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
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
  const subjectMock = dados?.razaoSocial ?? "FiscalAI Demo Ltda";
  const certificadoCompleto = !!fileName;

  return (
    <div className="flex flex-col gap-5">
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
          "flex flex-col items-center gap-3 p-8 rounded-md border-2 border-dashed transition-colors text-left w-full",
          arrastando
            ? "border-[var(--color-lime)] bg-[var(--color-lime-d)]"
            : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
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
          className="size-12 rounded-md grid place-items-center"
          style={{ background: "var(--color-card-3)" }}
        >
          <Upload className="size-5 text-[var(--color-lime)]" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-[var(--color-txt)]">
            {fileName ? fileName : "Arraste seu certificado aqui ou clique para selecionar"}
          </p>
          <p className="text-xs text-[var(--color-txt-3)] mt-1">
            Aceitamos arquivos .pfx ou .p12 (certificado A1).
          </p>
        </div>
      </button>

      {fileName ? (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="senha-cert">Senha do certificado</Label>
          <Input
            id="senha-cert"
            type="password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </div>
      ) : null}

      {certificadoCompleto ? (
        <div
          className="rounded-md border p-4 flex items-start gap-3"
          style={{
            background: "var(--color-lime-d)",
            borderColor: "rgba(163, 255, 107, 0.32)",
          }}
        >
          <ShieldCheck className="size-5 text-[var(--color-lime)] mt-0.5" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[var(--color-txt)]">
                Certificado válido
              </span>
              <Pill tom="ok">a1</Pill>
            </div>
            <p className="text-xs text-[var(--color-txt-2)] mt-0.5">
              {subjectMock} · válido até <span className="mono">{validade}</span>
            </p>
          </div>
        </div>
      ) : null}

      <div
        className="rounded-md border p-3 flex items-start gap-2.5"
        style={{
          background: "var(--color-card-2)",
          borderColor: "var(--color-line-2)",
        }}
      >
        <FileLock2 className="size-4 text-[var(--color-blue)] mt-0.5" />
        <p className="text-xs text-[var(--color-txt-2)] leading-relaxed">
          Sem certificado, você ainda usa todos os relatórios e o assistente. Só
          não consegue emitir nota fiscal por aqui — pode pular agora e adicionar
          depois.
        </p>
      </div>

      <div className="flex items-center justify-between pt-2">
        <Button variant="ghost" onClick={pular}>
          {pulado ? "Já vou pular" : "Pular por enquanto"}
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
