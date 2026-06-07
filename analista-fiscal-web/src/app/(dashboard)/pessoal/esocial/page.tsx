"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";
import { useQueryStates, parseAsString } from "nuqs";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { StatCard } from "@/components/shared/stat-card";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { StatusEventoPill } from "@/components/pessoal/status-evento-pill";
import {
  useEventosEsocial,
  useReenviarEvento,
} from "@/hooks/use-pessoal";
import { mensagemAmigavelPessoal } from "@/lib/api/pessoal";
import {
  TIPO_EVENTO_ESOCIAL_LABEL,
  type EventoEsocial,
} from "@/lib/schemas/pessoal";
import { formatarDataHoraBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function EsocialPage() {
  const { data, isLoading, isError, refetch } = useEventosEsocial();
  const reenviar = useReenviarEvento();
  const reduced = useReducedMotion();

  const [filtros, setFiltros] = useQueryStates(
    {
      q: parseAsString.withDefault(""),
      status: parseAsString.withDefault("todos"),
      tipo: parseAsString.withDefault("todos"),
    },
    { history: "replace" }
  );

  const lista = React.useMemo(() => {
    if (!data) return [];
    const q = filtros.q.trim().toLowerCase();
    return data.filter((e) => {
      if (filtros.status !== "todos" && e.status !== filtros.status) return false;
      if (filtros.tipo !== "todos" && e.tipo !== filtros.tipo) return false;
      if (q) {
        const alvo =
          `${e.funcionarioNome ?? ""} ${e.tipo} ${e.competencia} ${e.recibo ?? ""}`.toLowerCase();
        if (!alvo.includes(q)) return false;
      }
      return true;
    });
  }, [data, filtros]);

  const totais = React.useMemo(() => {
    const seed = { transmitido: 0, pendente: 0, erro: 0, rascunho: 0 };
    return (data ?? []).reduce(
      (acc, e) => {
        acc[e.status] += 1;
        return acc;
      },
      seed as Record<EventoEsocial["status"], number>
    );
  }, [data]);

  const erros = (data ?? []).filter((e) => e.status === "erro");

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        className="flex items-end justify-between gap-3 flex-wrap"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <div>
          <motion.span
            variants={itemV}
            className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
          >
            Pessoal · eSocial
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
          >
            Eventos do eSocial
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Cada admissão, demissão ou folha gera um evento aqui. Veja o que
            foi transmitido e o que precisa de correção.
          </motion.p>
        </div>
      </motion.header>

      <PessoalSubnav />

      {/* ── alerta de erros ── */}
      {erros.length > 0 ? (
        <Framed
          marks={false}
          tone="rule"
          surface="paper-2"
          className="flex flex-col md:flex-row md:items-center gap-3"
          style={{ borderColor: "var(--color-danger)" }}
        >
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0 text-[var(--color-danger)]" />
            <div>
              <p className="text-sm font-semibold text-[var(--color-ink)]">
                {erros.length} evento{erros.length > 1 ? "s" : ""} com erro
              </p>
              <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
                Reenvie agora para evitar pendências no fechamento da folha.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            className="shrink-0"
            disabled={reenviar.isPending}
            onClick={async () => {
              try {
                for (const evt of erros) {
                  await reenviar.mutateAsync(evt);
                }
                toast.success(
                  `${erros.length} evento${erros.length === 1 ? "" : "s"} reenviado${erros.length === 1 ? "" : "s"}`
                );
              } catch (err) {
                toast.error(mensagemAmigavelPessoal(err));
              }
            }}
          >
            {reenviar.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            Reenviar todos
          </Button>
        </Framed>
      ) : null}

      {/* ── totais ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Transmitidos"
          valor={String(totais.transmitido)}
          pill={{ tom: "ok", texto: "ok" }}
        />
        <StatCard
          label="Pendentes"
          valor={String(totais.pendente)}
          pill={{
            tom: totais.pendente > 0 ? "warn" : "neutral",
            texto: totais.pendente > 0 ? "transmitir" : "—",
          }}
        />
        <StatCard
          label="Com erro"
          valor={String(totais.erro)}
          pill={{
            tom: totais.erro > 0 ? "error" : "neutral",
            texto: totais.erro > 0 ? "atenção" : "—",
          }}
        />
        <StatCard
          label="Rascunhos"
          valor={String(totais.rascunho)}
          sub="Eventos não enviados"
        />
      </div>

      {/* ── filtros ── */}
      <Framed
        marks={false}
        tone="rule"
        surface="card"
        className="flex flex-col md:flex-row md:items-center gap-3"
      >
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
          <Input
            value={filtros.q}
            onChange={(e) => void setFiltros({ q: e.target.value })}
            placeholder="Buscar por funcionário, recibo ou competência"
            className="pl-9"
          />
        </div>
        <Select
          value={filtros.status}
          onValueChange={(v) => void setFiltros({ status: v })}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os status</SelectItem>
            <SelectItem value="transmitido">Transmitidos</SelectItem>
            <SelectItem value="pendente">Pendentes</SelectItem>
            <SelectItem value="erro">Com erro</SelectItem>
            <SelectItem value="rascunho">Rascunhos</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filtros.tipo}
          onValueChange={(v) => void setFiltros({ tipo: v })}
        >
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os tipos</SelectItem>
            {Object.entries(TIPO_EVENTO_ESOCIAL_LABEL).map(([cod, label]) => (
              <SelectItem key={cod} value={cod}>
                <abbr
                  title={`Código eSocial: ${cod}`}
                  className="no-underline mono text-[11px] text-[var(--color-ink-2)]"
                >
                  {cod}
                </abbr>
                {" — "}
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Framed>

      {/* ── conteúdo principal ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando eventos..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : lista.length === 0 ? (
        <EmptyState
          titulo="Nenhum evento"
          descricao="Ajuste os filtros ou aguarde a próxima folha."
        />
      ) : (
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo="Registro de eventos eSocial" size="sm" />
          </div>
          <Ruler />
          <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
            {lista.map((e) => (
              <LinhaEvento
                key={e.id}
                evento={e}
                aoReenviar={async () => {
                  try {
                    await reenviar.mutateAsync(e);
                    toast.success("Evento reenviado", {
                      description: "eSocial confirmou o recebimento.",
                    });
                  } catch (err) {
                    toast.error(mensagemAmigavelPessoal(err));
                  }
                }}
                reenviando={
                  reenviar.isPending && reenviar.variables?.id === e.id
                }
              />
            ))}
          </ul>
        </Framed>
      )}
    </motion.div>
  );
}

function LinhaEvento({
  evento,
  aoReenviar,
  reenviando,
}: {
  evento: EventoEsocial;
  aoReenviar: () => Promise<void>;
  reenviando?: boolean;
}) {
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex flex-col shrink-0 w-36 gap-1">
        <abbr
          title={`Código eSocial: ${evento.tipo} — ${TIPO_EVENTO_ESOCIAL_LABEL[evento.tipo]}`}
          className="no-underline mono text-xs font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {evento.tipo}
        </abbr>
        <StatusEventoPill status={evento.status} />
      </div>

      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm text-[var(--color-ink)] truncate">
          {TIPO_EVENTO_ESOCIAL_LABEL[evento.tipo]}
          {evento.funcionarioNome ? ` · ${evento.funcionarioNome}` : ""}
        </span>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-ink-3)] mono flex-wrap">
          <span style={{ fontVariantNumeric: "tabular-nums" }}>
            Competência {evento.competencia}
          </span>
          {evento.recibo ? (
            <>
              <span
                className="size-1 rounded-[var(--radius-sm)]"
                style={{ background: "var(--color-rule-2)" }}
              />
              <span>
                Recibo{" "}
                <span style={{ fontVariantNumeric: "tabular-nums" }}>
                  {evento.recibo}
                </span>
              </span>
            </>
          ) : null}
          {evento.transmitidoEm ? (
            <>
              <span
                className="size-1 rounded-[var(--radius-sm)]"
                style={{ background: "var(--color-rule-2)" }}
              />
              <span style={{ fontVariantNumeric: "tabular-nums" }}>
                {formatarDataHoraBR(evento.transmitidoEm)}
              </span>
            </>
          ) : null}
        </div>
        {evento.motivoErro ? (
          <span className="text-[11px] text-[var(--color-danger)] mt-0.5 flex items-center gap-1">
            <AlertTriangle className="size-3 shrink-0" />
            {evento.motivoErro}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {evento.status === "transmitido" ? (
          <span className="flex items-center gap-1 text-[11px] mono text-[var(--color-green)]">
            <CheckCircle2 className="size-3.5" /> ok
          </span>
        ) : null}
        {evento.status === "erro" || evento.status === "pendente" ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => void aoReenviar()}
            disabled={reenviando}
          >
            {reenviando ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            Reenviar
          </Button>
        ) : null}
      </div>
    </li>
  );
}
