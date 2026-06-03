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
import { Fig } from "@/components/blueprint/fig";
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
          <DialogTitle>Vincular transação ao livro contábil</DialogTitle>
          <DialogDescription>
            Selecione o lançamento correspondente. Sugestões com valor compatível
            (variação máxima 1%) e próximas da data.
          </DialogDescription>
        </DialogHeader>

        {/* Transação bancária — card Arkan */}
        <div
          className="rounded-[var(--radius-sm)] border p-3 flex items-start justify-between gap-3"
          style={{
            background: "var(--color-paper-2)",
            borderColor: "var(--color-rule)",
          }}
        >
          <div className="flex flex-col gap-1 min-w-0">
            <div className="flex items-center gap-2">
              <Pill tom={transacao.tipo === "credito" ? "ok" : "warn"}>
                {transacao.tipo === "credito" ? "entrada" : "saída"}
              </Pill>
              <span
                className="mono text-xs text-[var(--color-ink-2)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarDataBR(transacao.data)}
              </span>
            </div>
            <p className="text-sm font-semibold text-[var(--color-ink)] truncate">
              {transacao.descricao}
            </p>
            {transacao.contraparte ? (
              <p className="text-xs text-[var(--color-ink-2)] truncate">
                {transacao.contraparte}
              </p>
            ) : null}
          </div>
          <span
            className="mono text-lg font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={transacao.valor} />
          </span>
        </div>

        {/* Lista de sugestões */}
        <Fig n={1} titulo="Lançamentos sugeridos" size="sm" />
        <div className="flex flex-col gap-2 max-h-[320px] overflow-y-auto">
          {sugestoes.length === 0 ? (
            <p className="text-sm text-[var(--color-ink-2)] text-center py-6">
              Nenhuma sugestão encontrada. Ajuste o período ou crie um
              lançamento manual no Livro Diário.
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
            <Link2 className="size-4" /> Vincular selecionado
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
        "rounded-[var(--radius-sm)] border p-3 text-left transition-colors flex items-start justify-between gap-3",
        selecionado
          ? "border-[var(--color-green)] bg-[var(--color-paper-2)]"
          : "border-[var(--color-rule)] bg-[var(--color-paper-2)] hover:bg-[var(--color-paper)]"
      )}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--color-ink)] truncate">
          {lancamento.historico}
        </p>
        {/* Débito/crédito — cor+palavra, nunca só cor */}
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-ink-2)] mono mt-1 flex-wrap"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <span>
            <abbr title={`Débito: conta ${lancamento.contaDebito}`} className="no-underline">
              <span className="text-[var(--color-ochre)] font-bold">D</span>{" "}
              <span className="text-[var(--color-ink-2)]">{lancamento.contaDebito}</span>
            </abbr>{" "}
            {cD?.nome ?? ""}
          </span>
          <span aria-hidden className="text-[var(--color-ink-3)]">/</span>
          <span>
            <abbr title={`Crédito: conta ${lancamento.contaCredito}`} className="no-underline">
              <span className="text-[var(--color-green)] font-bold">C</span>{" "}
              <span className="text-[var(--color-ink-2)]">{lancamento.contaCredito}</span>
            </abbr>{" "}
            {cC?.nome ?? ""}
          </span>
        </div>
        <span
          className="mono text-[11px] text-[var(--color-ink-3)] mt-1 block"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarDataBR(lancamento.data)}
        </span>
      </div>
      <div className="flex flex-col items-end gap-2 shrink-0">
        <span
          className="mono text-sm font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={lancamento.valor} />
        </span>
        {selecionado ? (
          <Check className="size-4 text-[var(--color-green)]" />
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
