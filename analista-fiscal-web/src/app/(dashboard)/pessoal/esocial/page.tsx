"use client";

import * as React from "react";
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
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { StatCard } from "@/components/shared/stat-card";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { StatusEventoPill } from "@/components/pessoal/status-evento-pill";
import {
  useEventosEsocial,
  useReenviarEvento,
} from "@/hooks/use-pessoal";
import {
  TIPO_EVENTO_ESOCIAL_LABEL,
  type EventoEsocial,
} from "@/lib/schemas/pessoal";
import { formatarDataHoraBR } from "@/lib/format/data";

export default function EsocialPage() {
  const { data, isLoading, isError, refetch } = useEventosEsocial();
  const reenviar = useReenviarEvento();

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
        const alvo = `${e.funcionarioNome ?? ""} ${e.tipo} ${e.competencia} ${e.recibo ?? ""}`.toLowerCase();
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

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Pessoal · eSocial
          </span>
          <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Eventos do eSocial
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
            Cada admissão, demissão ou folha gera um evento. Aqui você vê o
            que foi transmitido, o que pode falhar e o que precisa de
            correção.
          </p>
        </div>
      </header>

      <PessoalSubnav />

      {erros.length > 0 ? (
        <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0" />
            <div>
              <AlertTitle>
                {erros.length} evento{erros.length > 1 ? "s" : ""} com erro
              </AlertTitle>
              <AlertDescription>
                Reenvie agora para evitar pendências no fechamento da folha.
              </AlertDescription>
            </div>
          </div>
          <Button
            className="shrink-0"
            disabled={reenviar.isPending}
            onClick={async () => {
              for (const evt of erros) {
                await reenviar.mutateAsync(evt);
              }
              toast.success(
                `${erros.length} evento${erros.length === 1 ? "" : "s"} reenviado${erros.length === 1 ? "" : "s"}`
              );
            }}
          >
            {reenviar.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            Reenviar todos
          </Button>
        </Alert>
      ) : null}

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

      <Card className="p-4 flex flex-col md:flex-row md:items-center gap-3">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-txt-3)]" />
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
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os tipos</SelectItem>
            {Object.entries(TIPO_EVENTO_ESOCIAL_LABEL).map(([cod, label]) => (
              <SelectItem key={cod} value={cod}>
                {cod} — {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Card>

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
        <Card className="overflow-hidden">
          <ul
            className="divide-y"
            style={{ borderColor: "var(--color-line)" }}
          >
            {lista.map((e) => (
              <LinhaEvento
                key={e.id}
                evento={e}
                aoReenviar={async () => {
                  await reenviar.mutateAsync(e);
                  toast.success("Evento reenviado", {
                    description: "eSocial confirmou o recebimento.",
                  });
                }}
                reenviando={reenviar.isPending && reenviar.variables?.id === e.id}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
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
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors">
      <div className="flex flex-col shrink-0 w-32">
        <span className="mono text-xs font-bold text-[var(--color-txt)]">
          {evento.tipo}
        </span>
        <StatusEventoPill status={evento.status} />
      </div>

      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm text-[var(--color-txt)] truncate">
          {TIPO_EVENTO_ESOCIAL_LABEL[evento.tipo]}
          {evento.funcionarioNome ? ` · ${evento.funcionarioNome}` : ""}
        </span>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-txt-3)] mono flex-wrap">
          <span>Competência {evento.competencia}</span>
          {evento.recibo ? (
            <>
              <span className="size-1 rounded-full bg-[var(--color-line-2)]" />
              <span>Recibo {evento.recibo}</span>
            </>
          ) : null}
          {evento.transmitidoEm ? (
            <>
              <span className="size-1 rounded-full bg-[var(--color-line-2)]" />
              <span>{formatarDataHoraBR(evento.transmitidoEm)}</span>
            </>
          ) : null}
        </div>
        {evento.motivoErro ? (
          <span className="text-[11px] text-[var(--color-red)] mt-0.5 flex items-center gap-1">
            <AlertTriangle className="size-3" />
            {evento.motivoErro}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {evento.status === "transmitido" ? (
          <span className="flex items-center gap-1 text-[11px] mono text-[var(--color-lime)]">
            <CheckCircle2 className="size-3.5" /> ok
          </span>
        ) : null}
        {evento.status === "erro" || evento.status === "pendente" ? (
          <Button
            variant="outline"
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
