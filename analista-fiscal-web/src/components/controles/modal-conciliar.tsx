"use client";

import * as React from "react";
import { Check, Link2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { useConciliarTransacao } from "@/hooks/use-controles";
import { useLancamentos } from "@/hooks/use-contabil";
import { buscarConta } from "@/lib/mocks/seeds/plano-contas";
import { formatarDataBR } from "@/lib/format/data";
import { cn } from "@/lib/utils";
import type { TransacaoBancaria } from "@/lib/schemas/controles";
import type { LancamentoContabil } from "@/lib/schemas/contabil";

interface Props {
  transacao: TransacaoBancaria | null;
  aberto: boolean;
  onAbertoChange: (v: boolean) => void;
}

export function ModalConciliar({ transacao, aberto, onAbertoChange }: Props) {
  const { data: lancamentos } = useLancamentos();
  const conciliar = useConciliarTransacao();
  const [selecionado, setSelecionado] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (aberto) setSelecionado(null);
  }, [aberto, transacao?.id]);

  if (!transacao) return null;

  const sugestoes = (lancamentos ?? [])
    .filter((l) => Math.abs(l.valor - transacao.valor) / transacao.valor < 0.01)
    .filter((l) => proximoNoTempo(l.data, transacao.data, 5))
    .sort((a, b) => Math.abs(diasEntre(a.data, transacao.data)) - Math.abs(diasEntre(b.data, transacao.data)))
    .slice(0, 8);

  return (
    <Dialog open={aberto} onOpenChange={onAbertoChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Conciliar transação</DialogTitle>
          <DialogDescription>
            Vincule esta movimentação bancária a um lançamento contábil. Listamos
            sugestões com valor compatível (± 1%) próximas da data.
          </DialogDescription>
        </DialogHeader>

        <div
          className="rounded-md border p-3 flex items-start justify-between gap-3"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
          }}
        >
          <div className="flex flex-col gap-1 min-w-0">
            <div className="flex items-center gap-2">
              <Pill tom={transacao.tipo === "credito" ? "ok" : "warn"}>
                {transacao.tipo === "credito" ? "entrada" : "saída"}
              </Pill>
              <span className="mono text-xs text-[var(--color-txt-3)]">
                {formatarDataBR(transacao.data)}
              </span>
            </div>
            <p className="text-sm font-semibold text-[var(--color-txt)] truncate">
              {transacao.descricao}
            </p>
            {transacao.contraparte ? (
              <p className="text-xs text-[var(--color-txt-3)] truncate">
                {transacao.contraparte}
              </p>
            ) : null}
          </div>
          <span className="mono text-lg font-bold text-[var(--color-txt)]">
            <Moeda valor={transacao.valor} />
          </span>
        </div>

        <div className="flex flex-col gap-2 max-h-[320px] overflow-y-auto">
          {sugestoes.length === 0 ? (
            <p className="text-sm text-[var(--color-txt-2)] text-center py-6">
              Nenhuma sugestão encontrada. Você pode marcar como conciliada
              manualmente ou criar um lançamento manual no Livro Diário.
            </p>
          ) : (
            sugestoes.map((l) => (
              <Sugestao
                key={l.id}
                lancamento={l}
                selecionado={selecionado === l.id}
                onSelecionar={() =>
                  setSelecionado(selecionado === l.id ? null : l.id)
                }
              />
            ))
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onAbertoChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!selecionado || conciliar.isPending}
            onClick={async () => {
              if (!selecionado) return;
              await conciliar.mutateAsync({
                transacaoId: transacao.id,
                lancamentoId: selecionado,
              });
              toast.success("Transação conciliada");
              onAbertoChange(false);
            }}
          >
            <Link2 className="size-4" /> Conciliar selecionado
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Sugestao({
  lancamento,
  selecionado,
  onSelecionar,
}: {
  lancamento: LancamentoContabil;
  selecionado: boolean;
  onSelecionar: () => void;
}) {
  const cD = buscarConta(lancamento.contaDebito);
  const cC = buscarConta(lancamento.contaCredito);
  return (
    <button
      type="button"
      onClick={onSelecionar}
      className={cn(
        "rounded-md border p-3 text-left transition-colors flex items-start justify-between gap-3",
        selecionado
          ? "border-[var(--color-lime)] bg-[var(--color-lime-d)]"
          : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
      )}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--color-txt)] truncate">
          {lancamento.historico}
        </p>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-txt-3)] mono mt-1 flex-wrap">
          <span className="text-[var(--color-amber)] font-bold">D</span>
          <span>{lancamento.contaDebito} {cD?.nome ?? ""}</span>
          <span className="text-[var(--color-lime)] font-bold">C</span>
          <span>{lancamento.contaCredito} {cC?.nome ?? ""}</span>
        </div>
        <span className="mono text-[11px] text-[var(--color-txt-3)] mt-1 block">
          {formatarDataBR(lancamento.data)}
        </span>
      </div>
      <div className="flex flex-col items-end gap-2">
        <span className="mono text-sm font-bold text-[var(--color-txt)]">
          <Moeda valor={lancamento.valor} />
        </span>
        {selecionado ? (
          <Check className="size-4 text-[var(--color-lime)]" />
        ) : null}
      </div>
    </button>
  );
}

function diasEntre(a: string, b: string): number {
  const da = new Date(a).getTime();
  const db = new Date(b).getTime();
  return (da - db) / (24 * 60 * 60 * 1000);
}

function proximoNoTempo(a: string, b: string, dias: number): boolean {
  return Math.abs(diasEntre(a, b)) <= dias;
}
