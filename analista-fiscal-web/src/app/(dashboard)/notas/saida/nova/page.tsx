"use client";

import * as React from "react";
import { NfWizardShell } from "@/components/notas/emitir/nf-wizard-shell";
import { PassoDestinatario } from "@/components/notas/emitir/passo-destinatario";
import { PassoItens } from "@/components/notas/emitir/passo-itens";
import { PassoPagamento } from "@/components/notas/emitir/passo-pagamento";
import { PassoEmissao } from "@/components/notas/emitir/passo-emissao";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";

const PASSOS = [
  { numero: 1, titulo: "Destinatário" },
  { numero: 2, titulo: "Itens" },
  { numero: 3, titulo: "Pagamento" },
  { numero: 4, titulo: "Emissão" },
];

export default function EmitirNotaPage() {
  const passo = useNfWizardStore((s) => s.passo);
  const resetar = useNfWizardStore((s) => s.resetar);

  React.useEffect(() => {
    return () => {
      // Mantém o draft entre navegações para o usuário não perder.
      // Reset explícito ocorre via "Emitir outra nota".
    };
  }, [resetar]);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo notas
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Emitir nota fiscal
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Em 4 passos. Sistema calcula CFOP, NCM, CST e alíquotas pra você.
        </p>
      </header>

      <NfWizardShell passos={PASSOS} passoAtual={passo}>
        {passo === 1 ? <PassoDestinatario /> : null}
        {passo === 2 ? <PassoItens /> : null}
        {passo === 3 ? <PassoPagamento /> : null}
        {passo === 4 ? <PassoEmissao /> : null}
      </NfWizardShell>
    </div>
  );
}
