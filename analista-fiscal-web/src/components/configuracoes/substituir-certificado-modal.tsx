"use client";

import * as React from "react";
import { Upload, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import type { Empresa } from "@/lib/schemas/empresa";
import { cn } from "@/lib/utils";

export function SubstituirCertificadoModal({
  open,
  onOpenChange,
  empresa,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  empresa: Empresa;
}) {
  const { salvarEmpresa } = useEmpresaAtual();
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [arrastando, setArrastando] = React.useState(false);
  const [arquivo, setArquivo] = React.useState<string | null>(null);
  const [senha, setSenha] = React.useState("");
  const [enviando, setEnviando] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setArquivo(null);
      setSenha("");
      setEnviando(false);
    }
  }, [open]);

  function handleFile(file: File | null) {
    if (!file) return;
    setArquivo(file.name);
  }

  async function confirmar() {
    if (!arquivo) return;
    setEnviando(true);
    try {
      const validade = new Date();
      validade.setFullYear(validade.getFullYear() + 1);
      await salvarEmpresa({
        ...empresa,
        certificadoA1: {
          nomeArquivo: arquivo,
          validade: validade.toISOString().slice(0, 10),
          mock: true,
        },
      });
      toast.success("Certificado substituído", {
        description: "Já pode emitir NF-e com o novo A1.",
      });
      onOpenChange(false);
    } catch {
      toast.error("Não foi possível substituir agora.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div
              className="size-9 rounded-[var(--radius-sm)] grid place-items-center mt-0.5 border"
              style={{ background: "var(--color-paper-2)", borderColor: "var(--color-rule)" }}
            >
              <ShieldCheck className="size-4 text-[var(--color-green)]" />
            </div>
            <div className="flex-1">
              <DialogTitle>Substituir certificado A1</DialogTitle>
              <DialogDescription className="mt-1">
                Faça upload do novo arquivo .pfx ou .p12 e informe a senha.
                O anterior é arquivado automaticamente.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

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
            handleFile(e.dataTransfer.files[0] ?? null);
          }}
          className={cn(
            "flex flex-col items-center gap-3 p-6 rounded-[var(--radius-md)] border-2 border-dashed transition-colors text-left w-full",
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
            className="size-10 rounded-[var(--radius-sm)] grid place-items-center border"
            style={{ background: "var(--color-paper-2)", borderColor: "var(--color-rule)" }}
          >
            <Upload className="size-4 text-[var(--color-green)]" />
          </div>
          <p className="text-sm font-semibold text-[var(--color-ink)] text-center">
            {arquivo ? arquivo : "Arraste o certificado ou clique para selecionar"}
          </p>
          <p className="text-[11px] text-[var(--color-ink-3)]">
            .pfx ou .p12 — certificado A1
          </p>
        </button>

        {arquivo ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="senha-novo-cert">Senha do certificado</Label>
            <Input
              id="senha-novo-cert"
              type="password"
              placeholder="••••••••"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
            />
          </div>
        ) : null}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={enviando}
          >
            Cancelar
          </Button>
          <Button
            onClick={() => void confirmar()}
            disabled={!arquivo || enviando}
          >
            {enviando ? "Substituindo..." : "Substituir certificado"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
