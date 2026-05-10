"use client";

import * as React from "react";
import { Loader2, ShieldCheck, Lock, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { formatarMoeda } from "@/lib/format/moeda";
import type { BancoOpenFinance } from "@/lib/mocks/seeds/bancos-openfinance";

type Etapa = "intro" | "redirecionando" | "autorizando" | "sincronizando" | "pronto";

interface Props {
  banco: BancoOpenFinance | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSucesso: (saldo: number, apelido: string) => void;
}

export function BancoConectarModal({ banco, open, onOpenChange, onSucesso }: Props) {
  const [etapa, setEtapa] = React.useState<Etapa>("intro");
  const [saldo, setSaldo] = React.useState(0);

  React.useEffect(() => {
    if (!open) {
      setEtapa("intro");
      return;
    }
    setEtapa("intro");
  }, [open, banco?.id]);

  if (!banco) return null;

  async function fluxoAutomatico() {
    setEtapa("redirecionando");
    await sleep(1000);
    setEtapa("autorizando");
  }

  async function aoAutorizar() {
    setEtapa("sincronizando");
    await sleep(1500);
    const novoSaldo = 8_000 + Math.random() * 90_000;
    setSaldo(novoSaldo);
    setEtapa("pronto");
    await sleep(800);
    onSucesso(novoSaldo, `${banco?.nome} · Conta principal`);
    onOpenChange(false);
  }

  function fechar() {
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle className="sr-only">Conectar com {banco.nome}</DialogTitle>
        <div
          className="-m-6 mb-3 px-6 py-4 flex items-center gap-3"
          style={{ background: banco.cor, color: banco.textoCor }}
        >
          <div
            className="size-10 rounded-md grid place-items-center font-bold"
            style={{
              background: banco.textoCor === "#ffffff" ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.12)",
            }}
          >
            {banco.iniciais}
          </div>
          <div className="flex-1">
            <p className="text-sm font-bold leading-none">{banco.nome}</p>
            <p className="text-[10px] mono uppercase tracking-[0.16em] mt-1 opacity-80">
              Open Finance · BCB
            </p>
          </div>
          <button
            type="button"
            onClick={fechar}
            className="p-1 rounded-md transition-colors"
            style={{ color: banco.textoCor }}
            aria-label="Fechar"
          >
            <X className="size-4" />
          </button>
        </div>

        {etapa === "intro" ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-[var(--color-txt)]">
              Você será redirecionado pro app do <strong>{banco.nome}</strong> para
              autorizar o FiscalAI a ler suas transações.
            </p>
            <ul className="flex flex-col gap-2 text-xs text-[var(--color-txt-2)]">
              <li className="flex items-center gap-2">
                <ShieldCheck className="size-3.5 text-[var(--color-lime)]" />
                Conexão regulada pelo Banco Central — você pode revogar a qualquer momento.
              </li>
              <li className="flex items-center gap-2">
                <Lock className="size-3.5 text-[var(--color-lime)]" />
                Acesso somente leitura. O FiscalAI nunca movimenta sua conta.
              </li>
            </ul>
            <Button onClick={fluxoAutomatico} className="w-full mt-2">
              Continuar para o {banco.nome}
            </Button>
          </div>
        ) : null}

        {etapa === "redirecionando" ? (
          <PassoCarregando
            mensagem={`Conectando ao ${banco.nome} via Open Finance...`}
          />
        ) : null}

        {etapa === "autorizando" ? (
          <div
            className="rounded-md border p-5 flex flex-col gap-4"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            <div className="flex flex-col items-center gap-2 text-center">
              <span className="text-xs uppercase tracking-[0.14em] mono font-bold text-[var(--color-txt-3)]">
                {banco.nome}
              </span>
              <h3 className="text-base font-bold text-[var(--color-txt)]">
                Autorizar acesso ao FiscalAI?
              </h3>
              <p className="text-xs text-[var(--color-txt-2)] leading-relaxed">
                O FiscalAI poderá visualizar suas transações pelos próximos 12
                meses. Sem permissão para mover dinheiro.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={fechar}
                className="flex-1"
              >
                Recusar
              </Button>
              <Button onClick={aoAutorizar} className="flex-1">
                Autorizar
              </Button>
            </div>
          </div>
        ) : null}

        {etapa === "sincronizando" ? (
          <PassoCarregando
            mensagem="Aguarde, sincronizando saldo e transações..."
          />
        ) : null}

        {etapa === "pronto" ? (
          <div className="flex flex-col items-center gap-2 text-center py-3">
            <Pill tom="ok">conectado</Pill>
            <p className="text-base font-bold text-[var(--color-txt)]">
              {banco.nome} · Conta principal
            </p>
            <p className="mono text-sm text-[var(--color-txt-2)]">
              Saldo {formatarMoeda(saldo)}
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function PassoCarregando({ mensagem }: { mensagem: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-6">
      <Loader2
        className="size-6 animate-spin"
        style={{ color: "var(--color-lime)" }}
      />
      <p className="text-sm text-[var(--color-txt-2)]">{mensagem}</p>
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
