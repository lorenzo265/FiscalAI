"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, Check, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { BANCOS_OPENFINANCE, type BancoOpenFinance } from "@/lib/mocks/seeds/bancos-openfinance";
import { formatarMoeda } from "@/lib/format/moeda";
import { BancoConectarModal } from "./banco-conectar-modal";
import { cn } from "@/lib/utils";

export function PassoBancos() {
  const conectados = useOnboardingStore((s) => s.bancosConectados);
  const conectar = useOnboardingStore((s) => s.conectarBanco);
  const desconectar = useOnboardingStore((s) => s.desconectarBanco);
  const proximo = useOnboardingStore((s) => s.proximo);
  const voltar = useOnboardingStore((s) => s.voltar);

  const [bancoSelecionado, setBancoSelecionado] = React.useState<BancoOpenFinance | null>(
    null
  );

  function handleConectado(saldo: number, apelido: string) {
    if (!bancoSelecionado) return;
    conectar({
      id: bancoSelecionado.id,
      banco: bancoSelecionado.nome,
      apelido,
      saldo,
      logoVar: bancoSelecionado.cor,
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {BANCOS_OPENFINANCE.map((b) => {
          const ativo = conectados.find((c) => c.id === b.id);
          return (
            <button
              key={b.id}
              type="button"
              onClick={() => {
                if (ativo) {
                  desconectar(b.id);
                } else {
                  setBancoSelecionado(b);
                }
              }}
              className={cn(
                "rounded-md border p-3 transition-all text-left flex flex-col gap-2.5",
                ativo
                  ? "border-[var(--color-lime)] bg-[var(--color-lime-d)]"
                  : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div
                  className="px-2.5 py-1.5 rounded-md font-bold text-xs"
                  style={{ background: b.cor, color: b.textoCor }}
                >
                  {b.iniciais}
                </div>
                {ativo ? (
                  <Check className="size-4 text-[var(--color-lime)]" />
                ) : (
                  <Plus className="size-4 text-[var(--color-txt-3)]" />
                )}
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-txt)]">
                  {b.nome}
                </p>
                {ativo ? (
                  <p className="mono text-[10px] text-[var(--color-txt-2)] mt-0.5">
                    {formatarMoeda(ativo.saldo)}
                  </p>
                ) : (
                  <p className="text-[10px] text-[var(--color-txt-3)] mt-0.5">
                    Open Finance
                  </p>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {conectados.length > 0 ? (
        <div
          className="rounded-md border p-3 flex items-center gap-2.5 text-sm"
          style={{
            background: "var(--color-lime-d)",
            borderColor: "rgba(163, 255, 107, 0.32)",
          }}
        >
          <Pill tom="ok">{conectados.length} conta{conectados.length === 1 ? "" : "s"}</Pill>
          <span className="text-[var(--color-txt)]">
            Saldo total: <span className="mono font-semibold">
              {formatarMoeda(conectados.reduce((acc, b) => acc + b.saldo, 0))}
            </span>
          </span>
        </div>
      ) : (
        <p className="text-xs text-[var(--color-txt-2)]">
          Você pode pular essa etapa e conectar bancos depois pelo menu Controles.
        </p>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button variant="outline" onClick={voltar}>
          <ArrowLeft className="size-4" /> Voltar
        </Button>
        <Button onClick={proximo}>
          Continuar <ArrowRight className="size-4" />
        </Button>
      </div>

      <BancoConectarModal
        banco={bancoSelecionado}
        open={!!bancoSelecionado}
        onOpenChange={(v) => {
          if (!v) setBancoSelecionado(null);
        }}
        onSucesso={handleConectado}
      />
    </div>
  );
}
