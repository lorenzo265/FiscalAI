"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Inbox, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { NotasSubnav } from "@/components/notas/notas-subnav";
import {
  ManifestoPill,
  StatusNotaPill,
} from "@/components/notas/status-pill";
import { useManifestar, useNotas } from "@/hooks/use-notas";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarDataBR } from "@/lib/format/data";
import type { NotaFiscal, StatusManifesto } from "@/lib/schemas/nota";

const OPCOES_MANIFESTO: Array<{
  id: StatusManifesto;
  titulo: string;
  descricao: string;
  recomendado?: boolean;
}> = [
  {
    id: "confirmada",
    titulo: "Confirmação da operação",
    descricao:
      "Você reconhece a operação e confirma o recebimento das mercadorias / serviços. Mais seguro pra creditar imposto.",
    recomendado: true,
  },
  {
    id: "ciencia",
    titulo: "Ciência da operação",
    descricao:
      "Você toma ciência da NF-e mas ainda não confirmou o recebimento. Manifesto provisório.",
  },
  {
    id: "desconhecida",
    titulo: "Desconhecimento da operação",
    descricao:
      "Você não reconhece essa operação. Use quando uma NF-e foi emitida indevidamente em seu nome.",
  },
  {
    id: "nao_realizada",
    titulo: "Operação não realizada",
    descricao:
      "A operação consta como autorizada mas não foi efetivada (devolução, cancelamento informal, etc.).",
  },
];

export default function ManifestoEntradasPage() {
  const { data, isLoading, isError, refetch } = useNotas();
  const manifestar = useManifestar();
  const [alvo, setAlvo] = React.useState<NotaFiscal | null>(null);
  const [escolha, setEscolha] = React.useState<StatusManifesto>("confirmada");

  const entradas = (data ?? []).filter((n) => n.tipo === "entrada");
  const pendentes = entradas.filter(
    (n) => n.manifesto === "pendente_manifesto"
  );

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo notas
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Notas recebidas (manifesto)
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Manifeste as NF-e que você recebe — é assim que a Receita sabe que
          você reconhece a operação.
        </p>
      </header>

      <NotasSubnav />

      {pendentes.length > 0 ? (
        <Card
          className="p-5 flex items-center gap-4"
          style={{ background: "var(--color-amber-d)", borderColor: "rgba(255,184,77,0.32)" }}
        >
          <ShieldCheck className="size-6 text-[var(--color-amber)]" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-[var(--color-txt)]">
              {pendentes.length} nota(s) aguardando manifesto
            </span>
            <span className="text-[12px] text-[var(--color-txt-2)]">
              Você tem 180 dias da emissão pra manifestar. Sem isso, a Receita
              presume que você não reconhece a operação.
            </span>
          </div>
        </Card>
      ) : null}

      {isLoading ? (
        <LoadingState titulo="Carregando entradas..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : entradas.length === 0 ? (
        <EmptyState
          titulo="Nenhuma nota de entrada"
          descricao="Quando alguém emitir uma NF-e contra seu CNPJ, ela aparece aqui."
          icone={Inbox}
        />
      ) : (
        <Card className="overflow-hidden">
          <ul
            className="divide-y"
            style={{ borderColor: "var(--color-line)" }}
          >
            {entradas.map((n) => (
              <li
                key={n.id}
                className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors"
              >
                <div className="flex flex-col gap-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="mono text-sm font-bold text-[var(--color-txt)]">
                      Nº {n.numero}
                    </span>
                    <StatusNotaPill status={n.status} />
                    {n.manifesto ? <ManifestoPill manifesto={n.manifesto} /> : null}
                  </div>
                  <span className="text-sm text-[var(--color-txt)] truncate">
                    {n.razaoEmitente}
                  </span>
                  <span className="text-[11px] text-[var(--color-txt-3)] mono">
                    {formatarCNPJ(n.cnpjEmitente)} · emitida{" "}
                    {formatarDataBR(n.emitidaEm)}
                  </span>
                </div>

                <span className="mono text-base font-bold text-[var(--color-txt)] shrink-0">
                  <Moeda valor={n.totais.valorNota} />
                </span>

                <div className="flex items-center gap-2 shrink-0">
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/notas/${n.chave}`}>
                      Ver <ArrowRight className="size-3.5" />
                    </Link>
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      setAlvo(n);
                      setEscolha(
                        n.manifesto === "pendente_manifesto"
                          ? "confirmada"
                          : (n.manifesto ?? "confirmada")
                      );
                    }}
                  >
                    {n.manifesto && n.manifesto !== "pendente_manifesto"
                      ? "Atualizar manifesto"
                      : "Manifestar"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Dialog open={!!alvo} onOpenChange={(v) => !v && setAlvo(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Manifestar NF-e {alvo?.numero}</DialogTitle>
            <DialogDescription>
              Como você quer reagir a essa nota emitida em seu nome?
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-2">
            {OPCOES_MANIFESTO.map((op) => {
              const ativo = escolha === op.id;
              return (
                <button
                  key={op.id}
                  type="button"
                  onClick={() => setEscolha(op.id)}
                  className={
                    "text-left rounded-md border p-3 flex flex-col gap-1 transition-colors " +
                    (ativo
                      ? "border-[rgba(163,255,107,0.32)] bg-[var(--color-lime-d)]"
                      : "border-[var(--color-line-2)] hover:bg-[var(--color-card-2)]")
                  }
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        "size-3.5 rounded-full border-2 " +
                        (ativo
                          ? "bg-[var(--color-lime)] border-[var(--color-lime)]"
                          : "border-[var(--color-line-2)]")
                      }
                    />
                    <span className="text-sm font-semibold text-[var(--color-txt)]">
                      {op.titulo}
                    </span>
                    {op.recomendado ? (
                      <span className="ml-auto mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-lime)] font-bold">
                        recomendado
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[12px] text-[var(--color-txt-2)] leading-relaxed pl-6">
                    {op.descricao}
                  </p>
                </button>
              );
            })}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setAlvo(null)}>
              Cancelar
            </Button>
            <Button
              disabled={manifestar.isPending}
              onClick={async () => {
                if (!alvo) return;
                await manifestar.mutateAsync({
                  chave: alvo.chave,
                  manifesto: escolha,
                });
                toast.success("Manifesto enviado", {
                  description: `NF-e ${alvo.numero} agora está como ${escolha.replace("_", " ")}.`,
                });
                setAlvo(null);
              }}
            >
              Confirmar manifesto
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
