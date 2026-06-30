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
import { useSubirCertificado } from "@/hooks/use-certificado";
import { ApiError } from "@/lib/http";
import { cn } from "@/lib/utils";

/** Lê um File e devolve só o conteúdo em base64 (sem o prefixo data:). */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const virgula = result.indexOf(",");
      resolve(virgula >= 0 ? result.slice(virgula + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("falha ao ler o arquivo"));
    reader.readAsDataURL(file);
  });
}

export function SubstituirCertificadoModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const subir = useSubirCertificado();
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [arrastando, setArrastando] = React.useState(false);
  const [arquivo, setArquivo] = React.useState<File | null>(null);
  const [senha, setSenha] = React.useState("");

  React.useEffect(() => {
    if (!open) {
      setArquivo(null);
      setSenha("");
    }
  }, [open]);

  function handleFile(file: File | null) {
    if (!file) return;
    setArquivo(file);
  }

  async function confirmar() {
    if (!arquivo || !senha) return;
    try {
      const pfxBase64 = await fileToBase64(arquivo);
      await subir.mutateAsync({ pfxBase64, senha });
      toast.success("Certificado instalado", {
        description:
          "Guardado com segurança (cifrado). A transmissão é liberada quando você ativar cada envio.",
      });
      onOpenChange(false);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.mensagem
          : "Não foi possível enviar o certificado.";
      toast.error("Falha ao instalar", { description: msg });
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
              <DialogTitle>Instalar certificado A1</DialogTitle>
              <DialogDescription className="mt-1">
                Envie o arquivo .pfx ou .p12 e informe a senha. Conferimos a
                validade e o CNPJ, e guardamos tudo cifrado. O anterior é
                substituído automaticamente.
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
            {arquivo ? arquivo.name : "Arraste o certificado ou clique para selecionar"}
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
            disabled={subir.isPending}
          >
            Cancelar
          </Button>
          <Button
            onClick={() => void confirmar()}
            disabled={!arquivo || !senha || subir.isPending}
          >
            {subir.isPending ? "Instalando..." : "Instalar certificado"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
