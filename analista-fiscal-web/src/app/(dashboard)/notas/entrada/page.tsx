"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Inbox, ShieldCheck } from "lucide-react";
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
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { NotasSubnav } from "@/components/notas/notas-subnav";
import {
  ManifestoPill,
  StatusNotaPill,
} from "@/components/notas/status-pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useManifestar, useNotas } from "@/hooks/use-notas";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
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
      "Você reconhece a operação e confirma o recebimento das mercadorias / serviços. Mais seguro para creditar imposto.",
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
  const reduced = useReducedMotion();
  const [alvo, setAlvo] = React.useState<NotaFiscal | null>(null);
  const [escolha, setEscolha] = React.useState<StatusManifesto>("confirmada");

  const entradas = (data ?? []).filter((n) => n.tipo === "entrada");
  const pendentes = entradas.filter(
    (n) => n.manifesto === "pendente_manifesto"
  );

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageReveal}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Notas
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Notas recebidas
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          Manifeste as NF-e que você recebe — é assim que a Receita sabe que
          você reconhece a operação.
        </motion.p>
      </motion.header>

      <NotasSubnav />

      {/* ── alerta pendentes ── */}
      {pendentes.length > 0 ? (
        <Framed marks={false} tone="rule" surface="card" className="flex items-center gap-4"
          style={{ borderColor: "var(--color-ochre)", background: "color-mix(in srgb, var(--color-ochre) 8%, var(--color-card))" }}
        >
          <ShieldCheck
            className="size-5 shrink-0"
            style={{ color: "var(--color-ochre)" }}
          />
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-[var(--color-ink)]">
              {pendentes.length} nota(s) aguardando manifesto
            </span>
            <span className="text-[12px] text-[var(--color-ink-2)]">
              Você tem 180 dias da emissão para manifestar. Sem isso, a Receita
              presume que você não reconhece a operação.
            </span>
          </div>
        </Framed>
      ) : null}

      {/* ── lista ── */}
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
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo={`Entradas recebidas (${entradas.length})`} size="sm" />
          </div>
          <Ruler />
          <ul>
            {entradas.map((n, idx) => (
              <li
                key={n.id}
                className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-3 border-b last:border-b-0 transition-colors hover:bg-[var(--color-paper-2)]"
                style={{ borderColor: "var(--color-rule)" }}
              >
                {/* índice técnico */}
                <span
                  className="mono text-[10px] text-[var(--color-ink-3)] shrink-0 hidden md:block"
                  style={{ fontVariantNumeric: "tabular-nums", width: "2rem" }}
                >
                  {String(idx + 1).padStart(2, "0")}
                </span>

                <div className="flex flex-col gap-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="mono text-sm font-bold text-[var(--color-ink)]"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      Nº {n.numero}
                    </span>
                    <StatusNotaPill status={n.status} />
                    {n.manifesto ? (
                      <ManifestoPill manifesto={n.manifesto} />
                    ) : null}
                  </div>
                  <span className="text-sm text-[var(--color-ink)] truncate font-medium">
                    {n.razaoEmitente}
                  </span>
                  <span
                    className="text-[11px] text-[var(--color-ink-2)] mono"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {formatarCNPJ(n.cnpjEmitente)} · emitida{" "}
                    {formatarDataBR(n.emitidaEm)}
                  </span>
                </div>

                <span
                  className="mono text-base font-bold text-[var(--color-ink)] shrink-0"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
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
        </Framed>
      )}

      {/* ── Dialog manifesto ── */}
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
                    "text-left rounded-[var(--radius-md)] border p-3 flex flex-col gap-1 transition-colors " +
                    (ativo
                      ? "border-[var(--color-green)] bg-[var(--color-green-wash)]"
                      : "border-[var(--color-rule-2)] hover:bg-[var(--color-paper-2)]")
                  }
                >
                  <div className="flex items-center gap-2">
                    {/* indicador de seleção — quadrado técnico, não pílula */}
                    <span
                      className={
                        "size-3 rounded-[1px] border-2 shrink-0 transition-colors " +
                        (ativo
                          ? "bg-[var(--color-green)] border-[var(--color-green)]"
                          : "border-[var(--color-rule-2)]")
                      }
                    />
                    <span className="text-sm font-semibold text-[var(--color-ink)]">
                      {op.titulo}
                    </span>
                    {op.recomendado ? (
                      <span className="ml-auto mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-green)] font-bold">
                        recomendado
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[12px] text-[var(--color-ink-2)] leading-relaxed pl-5">
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
    </motion.div>
  );
}
