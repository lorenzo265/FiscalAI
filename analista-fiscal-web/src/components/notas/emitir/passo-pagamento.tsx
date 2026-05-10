"use client";

import { ArrowLeft, ArrowRight, CreditCard } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";
import type { FormaPagamento } from "@/lib/schemas/nota";

const FORMAS: Array<{ id: FormaPagamento; label: string }> = [
  { id: "pix", label: "PIX" },
  { id: "boleto", label: "Boleto bancário" },
  { id: "transferencia", label: "Transferência (TED/DOC)" },
  { id: "cartao_credito", label: "Cartão de crédito" },
  { id: "cartao_debito", label: "Cartão de débito" },
  { id: "dinheiro", label: "Dinheiro" },
  { id: "outros", label: "Outros" },
];

export function PassoPagamento() {
  const { pagamento, setPagamento, observacao, setObservacao, proximo, voltar } =
    useNfWizardStore();

  return (
    <Card className="p-5 flex flex-col gap-4 max-w-2xl">
      <div className="flex items-center gap-2">
        <CreditCard className="size-4 text-[var(--color-blue)]" />
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Como o cliente vai pagar?
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label>Forma de pagamento</Label>
          <Select
            value={pagamento.forma}
            onValueChange={(v) =>
              setPagamento({ forma: v as FormaPagamento })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FORMAS.map((f) => (
                <SelectItem key={f.id} value={f.id}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Vencimento</Label>
          <Input
            type="date"
            value={pagamento.vencimento}
            onChange={(e) => setPagamento({ vencimento: e.target.value })}
            className="mono"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Parcelas</Label>
          <Input
            type="number"
            min="1"
            max="24"
            value={pagamento.parcelas}
            onChange={(e) =>
              setPagamento({ parcelas: Number(e.target.value) || 1 })
            }
            className="mono"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Observação (opcional)</Label>
        <textarea
          value={observacao}
          onChange={(e) => setObservacao(e.target.value)}
          placeholder="Ex: Pagamento conforme proposta nº 1234. Em caso de atraso, juros de 1% a.m."
          rows={3}
          className="rounded-md border bg-[var(--color-card-2)] border-[var(--color-line-2)] px-3 py-2 text-sm text-[var(--color-txt)] placeholder:text-[var(--color-txt-3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-lime)]/30"
        />
      </div>

      <div
        className="flex justify-between items-center pt-2 border-t"
        style={{ borderColor: "var(--color-line)" }}
      >
        <Button variant="ghost" onClick={voltar}>
          <ArrowLeft className="size-3.5" /> Voltar
        </Button>
        <Button onClick={proximo} size="lg">
          Continuar <ArrowRight className="size-4" />
        </Button>
      </div>
    </Card>
  );
}
