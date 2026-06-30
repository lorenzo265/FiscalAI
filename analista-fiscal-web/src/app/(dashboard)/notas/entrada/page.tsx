"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Inbox, RefreshCw, ShieldCheck } from "lucide-react";
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
import {
  useDestinadas,
  useManifestar,
  useNotas,
  useRegistrarManifesto,
  useSincronizarDestinadas,
} from "@/hooks/use-notas";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { ApiError } from "@/lib/http";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarDataBR } from "@/lib/format/data";
import type { ManifestoEnviavel } from "@/lib/api/manifestacao";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import type { NotaFiscal, StatusManifesto } from "@/lib/schemas/nota";

const OPCOES_MANIFESTO: Array<{
  id: ManifestoEnviavel;
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
      "A operação consta como autorizada mas não foi efetivada (devolução, cancelamento informal, etc.). Exige uma justificativa.",
  },
];

const TEXTO_MANIFESTO: Record<ManifestoEnviavel, string> = {
  confirmada: "confirmada",
  ciencia: "ciência",
  desconhecida: "desconhecida",
  nao_realizada: "operação não realizada",
};

/** Alvo unificado do modal: uma nota importada (Dexie) ou uma destinada (backend). */
type AlvoManifesto = {
  chave: string;
  rotulo: string;
  origem: "importada" | "destinada";
};

export default function ManifestoEntradasPage() {
  const { data, isLoading, isError, refetch } = useNotas();
  const { empresa } = useEmpresaAtual();

  const destinadasQuery = useDestinadas(true);
  const sincronizar = useSincronizarDestinadas();
  const manifestarLocal = useManifestar(); // legado: notas importadas (Dexie)
  const registrarBackend = useRegistrarManifesto(); // backend MD-e real

  const reduced = useReducedMotion();
  const [alvo, setAlvo] = React.useState<AlvoManifesto | null>(null);
  const [escolha, setEscolha] =
    React.useState<ManifestoEnviavel>("confirmada");
  const [justificativa, setJustificativa] = React.useState("");

  const entradas = (data ?? []).filter((n) => n.tipo === "entrada");
  const destinadas = destinadasQuery.data ?? [];

  const enviando = manifestarLocal.isPending || registrarBackend.isPending;
  const precisaJustificativa = escolha === "nao_realizada";
  const jLen = justificativa.trim().length;
  const justificativaValida =
    !precisaJustificativa || (jLen >= 15 && jLen <= 255);

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  function abrir(alvoNovo: AlvoManifesto, atual?: StatusManifesto) {
    setAlvo(alvoNovo);
    setEscolha(
      atual && atual !== "pendente_manifesto"
        ? (atual as ManifestoEnviavel)
        : "confirmada"
    );
    setJustificativa("");
  }

  async function confirmarManifesto() {
    if (!alvo) return;
    try {
      if (alvo.origem === "destinada") {
        if (!empresa) {
          throw new ApiError(
            0,
            "EmpresaNaoSelecionada",
            "Selecione uma empresa antes de manifestar."
          );
        }
        await registrarBackend.mutateAsync({
          chaveNfe: alvo.chave,
          cnpjDestinatario: empresa.cnpj,
          manifesto: escolha,
          justificativa: precisaJustificativa
            ? justificativa.trim()
            : undefined,
        });
      } else {
        await manifestarLocal.mutateAsync({
          chave: alvo.chave,
          manifesto: escolha,
        });
      }
      toast.success("Manifesto enviado", {
        description: `${alvo.rotulo} agora está como ${TEXTO_MANIFESTO[escolha]}.`,
      });
      setAlvo(null);
      setJustificativa("");
    } catch (err) {
      toast.error("Não foi possível manifestar", {
        description:
          err instanceof ApiError
            ? err.mensagem
            : "Tente novamente em instantes.",
      });
    }
  }

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

      {/* ── seção "Na Receita" (DistribuiçãoDFe) — número-herói + sincronizar ── */}
      <Framed
        marks={false}
        tone="rule"
        surface="card"
        className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex items-center gap-4">
          <span
            className="mono text-[56px] md:text-[64px] leading-none font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {destinadasQuery.isLoading ? "—" : destinadas.length}
          </span>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-[var(--color-ink)]">
              NF-e na Receita aguardando manifesto
            </span>
            <span className="text-[12px] text-[var(--color-ink-2)] max-w-sm">
              Notas emitidas contra seu CNPJ que a Receita conhece. Você tem 180
              dias da emissão para manifestar.
            </span>
            {destinadasQuery.isError ? (
              <span className="text-[11px] text-[var(--color-ochre)] mt-1">
                Não foi possível consultar a Receita agora. Tente sincronizar.
              </span>
            ) : null}
          </div>
        </div>
        <Button
          onClick={async () => {
            try {
              const r = await sincronizar.mutateAsync();
              toast.success("Sincronização concluída", {
                description:
                  r.novos > 0
                    ? `${r.novos} nova(s) NF-e encontrada(s) na Receita.`
                    : "Nenhuma NF-e nova desde a última consulta.",
              });
            } catch (err) {
              toast.error("Falha ao sincronizar", {
                description:
                  err instanceof ApiError
                    ? err.mensagem
                    : "Não foi possível consultar a Receita.",
              });
            }
          }}
          disabled={sincronizar.isPending}
          className="shrink-0"
        >
          <RefreshCw
            className={"size-4 " + (sincronizar.isPending ? "animate-spin" : "")}
          />
          {sincronizar.isPending ? "Sincronizando…" : "Sincronizar"}
        </Button>
      </Framed>

      {/* ── lista de destinadas (descobertas, a manifestar) ── */}
      {destinadas.length > 0 ? (
        <Framed
          marks={false}
          tone="ink"
          surface="card"
          padded={false}
          className="overflow-hidden"
        >
          <div className="px-5 pt-4 pb-2">
            <Fig
              n={1}
              titulo={`Na Receita, a manifestar (${destinadas.length})`}
              size="sm"
            />
          </div>
          <Ruler />
          <ul>
            {destinadas.map((d) => (
              <li
                key={d.id}
                className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-3 border-b last:border-b-0 transition-colors hover:bg-[var(--color-paper-2)]"
                style={{ borderColor: "var(--color-rule)" }}
              >
                <div className="flex flex-col gap-1 flex-1 min-w-0">
                  <span className="text-sm text-[var(--color-ink)] truncate font-medium">
                    {d.emitenteNome ?? "Emitente não identificado"}
                  </span>
                  <span
                    className="text-[11px] text-[var(--color-ink-2)] mono"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {d.emitenteCnpj ? formatarCNPJ(d.emitenteCnpj) : "—"}
                    {d.dhEmissao ? ` · emitida ${formatarDataBR(d.dhEmissao)}` : ""}
                  </span>
                  <span
                    className="text-[10px] text-[var(--color-ink-3)] mono truncate"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                    title={d.chaveNfe}
                  >
                    {d.chaveNfe}
                  </span>
                </div>

                <span
                  className="mono text-base font-bold text-[var(--color-ink)] shrink-0"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  <Moeda valor={Number(d.valorTotal ?? 0)} />
                </span>

                <Button
                  size="sm"
                  className="shrink-0"
                  onClick={() =>
                    abrir({
                      chave: d.chaveNfe,
                      rotulo: d.emitenteNome ?? "NF-e da Receita",
                      origem: "destinada",
                    })
                  }
                >
                  Manifestar
                </Button>
              </li>
            ))}
          </ul>
        </Framed>
      ) : null}

      {/* ── lista de notas importadas (XML) ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando entradas..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : entradas.length === 0 ? (
        destinadas.length === 0 ? (
          <EmptyState
            titulo="Nenhuma nota de entrada"
            descricao="Quando alguém emitir uma NF-e contra seu CNPJ, ela aparece aqui — sincronize para buscar na Receita."
            icone={Inbox}
          />
        ) : null
      ) : (
        <Framed
          marks={false}
          tone="ink"
          surface="card"
          padded={false}
          className="overflow-hidden"
        >
          <div className="px-5 pt-4 pb-2">
            <Fig
              n={2}
              titulo={`Importadas por XML (${entradas.length})`}
              size="sm"
            />
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
                    onClick={() =>
                      abrir(
                        {
                          chave: n.chave,
                          rotulo: `NF-e ${n.numero}`,
                          origem: "importada",
                        },
                        n.manifesto
                      )
                    }
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

      {/* ── Dialog manifesto (unificado) ── */}
      <Dialog
        open={!!alvo}
        onOpenChange={(v) => {
          if (!v) {
            setAlvo(null);
            setJustificativa("");
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Manifestar {alvo?.rotulo}</DialogTitle>
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

          {/* justificativa — obrigatória só para "operação não realizada" (210240) */}
          {precisaJustificativa ? (
            <div className="flex flex-col gap-1">
              <label
                htmlFor="justificativa-manifesto"
                className="text-[12px] font-semibold text-[var(--color-ink)]"
              >
                Justificativa{" "}
                <span className="text-[var(--color-ink-3)] font-normal">
                  (15 a 255 caracteres)
                </span>
              </label>
              <textarea
                id="justificativa-manifesto"
                value={justificativa}
                onChange={(e) => setJustificativa(e.target.value)}
                rows={3}
                maxLength={255}
                placeholder="Explique por que a operação não foi realizada."
                className="rounded-[var(--radius-md)] border border-[var(--color-rule-2)] bg-[var(--color-paper)] px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-green)]"
              />
              <span
                className="mono text-[10px] text-[var(--color-ink-3)] self-end"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {jLen}/255
              </span>
            </div>
          ) : null}

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setAlvo(null);
                setJustificativa("");
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={enviando || !justificativaValida}
              onClick={() => void confirmarManifesto()}
            >
              {enviando ? "Enviando…" : "Confirmar manifesto"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
