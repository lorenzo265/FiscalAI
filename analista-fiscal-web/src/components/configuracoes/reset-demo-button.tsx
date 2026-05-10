"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function ResetDemoButton() {
  const router = useRouter();
  const { resetar } = useEmpresaAtual();
  const [aberto, setAberto] = React.useState(false);
  const [resetando, setResetando] = React.useState(false);

  async function confirmar() {
    setResetando(true);
    try {
      await resetar();
      toast.success("Dados de demonstração apagados", {
        description: "Você vai recomeçar pelo cadastro da empresa.",
      });
      setAberto(false);
      router.replace("/onboarding");
    } catch {
      toast.error("Não foi possível resetar agora. Tente novamente.");
    } finally {
      setResetando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        className="text-[11px] text-[var(--color-txt-3)] hover:text-[var(--color-red)] transition-colors flex items-center gap-1.5"
      >
        <Trash2 className="size-3" />
        Limpar dados de demonstração
      </button>

      <Dialog open={aberto} onOpenChange={setAberto}>
        <DialogContent>
          <DialogHeader>
            <div className="flex items-start gap-3">
              <div
                className="size-9 rounded-md grid place-items-center mt-0.5"
                style={{ background: "var(--color-red-d)" }}
              >
                <AlertTriangle className="size-4 text-[var(--color-red)]" />
              </div>
              <div className="flex-1">
                <DialogTitle>Apagar todos os dados de demonstração?</DialogTitle>
                <DialogDescription className="mt-1">
                  Vamos zerar empresa, notas, lançamentos, bancos, folha,
                  compliance e o histórico do assistente. Você é redirecionado
                  para o onboarding e começa do zero.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={() => setAberto(false)}
              disabled={resetando}
            >
              Cancelar
            </Button>
            <Button
              onClick={() => void confirmar()}
              disabled={resetando}
              className="bg-[var(--color-red-d)] text-[var(--color-red)] border border-[rgba(255,85,102,0.32)] hover:bg-[var(--color-red)] hover:text-[var(--color-bg)]"
            >
              {resetando ? "Apagando..." : "Sim, apagar tudo"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
