"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { BancoLogo } from "@/components/controles/banco-logo";
import { BancoConectarModal } from "@/components/onboarding/banco-conectar-modal";
import { useBancos, useConectarBanco } from "@/hooks/use-controles";
import {
  BANCOS_OPENFINANCE,
  type BancoOpenFinance,
} from "@/lib/mocks/seeds/bancos-openfinance";
import { cn } from "@/lib/utils";

export default function ConectarBancoPage() {
  const router = useRouter();
  const { data: contasConectadas } = useBancos();
  const conectar = useConectarBanco();

  const [bancoSelecionado, setBancoSelecionado] =
    React.useState<BancoOpenFinance | null>(null);

  async function aoSucesso() {
    if (!bancoSelecionado) return;
    try {
      const conta = await conectar.mutateAsync(bancoSelecionado.id);
      toast.success(`${conta.bancoNome} conectado`, {
        description: "30 dias de transações importados.",
      });
      setBancoSelecionado(null);
      router.push("/controles/bancos");
    } catch {
      toast.error("Não foi possível concluir a conexão.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Button asChild variant="ghost" className="self-start -ml-2">
          <Link href="/controles/bancos">
            <ArrowLeft className="size-4" /> Voltar para bancos
          </Link>
        </Button>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Controles · Conectar conta
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Conectar uma conta bancária
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl">
          Selecione seu banco abaixo. Você será redirecionado para autorizar o
          FiscalAI via Open Finance — acesso somente leitura, regulado pelo
          Banco Central.
        </p>
      </header>

      <ControlesSubnav />

      <Card
        className="flex items-center gap-3 p-4 border"
        style={{
          background: "var(--color-lime-d)",
          borderColor: "rgba(163, 255, 107, 0.22)",
        }}
      >
        <ShieldCheck
          className="size-5 shrink-0"
          style={{ color: "var(--color-lime)" }}
        />
        <p className="text-sm text-[var(--color-txt)]">
          Open Finance é o protocolo do Banco Central que permite conectar
          contas com segurança. O FiscalAI <strong>nunca</strong> movimenta seu
          dinheiro — só lê o extrato.
        </p>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {BANCOS_OPENFINANCE.map((banco) => {
          const jaConectado = contasConectadas?.some(
            (c) => c.bancoId === banco.id
          );
          return (
            <button
              key={banco.id}
              type="button"
              disabled={jaConectado}
              onClick={() => setBancoSelecionado(banco)}
              className={cn(
                "rounded-md border p-4 transition-all text-left flex flex-col gap-3",
                jaConectado
                  ? "border-[var(--color-lime)] bg-[var(--color-lime-d)] cursor-default"
                  : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)] hover:border-[var(--color-line)]"
              )}
            >
              <div className="flex items-center justify-between">
                <BancoLogo
                  cor={banco.cor}
                  textoCor={banco.textoCor}
                  iniciais={banco.iniciais}
                  size="md"
                />
                {jaConectado ? (
                  <span className="mono text-[9px] uppercase tracking-[0.16em] font-bold text-[var(--color-lime)]">
                    conectado
                  </span>
                ) : null}
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-txt)]">
                  {banco.nome}
                </p>
                <p className="text-[11px] text-[var(--color-txt-3)] mt-0.5">
                  {jaConectado ? "Conta já vinculada" : "Open Finance · BCB"}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      <BancoConectarModal
        banco={bancoSelecionado}
        open={!!bancoSelecionado}
        onOpenChange={(v) => {
          if (!v) setBancoSelecionado(null);
        }}
        onSucesso={() => {
          void aoSucesso();
        }}
      />
    </div>
  );
}
