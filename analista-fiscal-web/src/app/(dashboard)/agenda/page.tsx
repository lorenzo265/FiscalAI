"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Calendar, List } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { CalendarioMes } from "@/components/agenda/calendario-mes";
import {
  COR_STATUS_AGENDA,
  StatusEventoAgendaPill,
} from "@/components/agenda/status-evento-pill";
import { useAgendaAno, useAgendaMes } from "@/hooks/use-agenda";
import { formatarDataBR, formatarMesAnoBR } from "@/lib/format/data";
import type { EventoAgenda } from "@/lib/schemas/agenda";
import { cn } from "@/lib/utils";

export default function AgendaPage() {
  const hoje = React.useMemo(() => new Date(), []);
  const [ano, setAno] = React.useState(hoje.getFullYear());
  const [mes, setMes] = React.useState(hoje.getMonth() + 1);
  const [modo, setModo] = React.useState<"mes" | "ano">("mes");

  const {
    data: eventosMes,
    isLoading: loadMes,
    isError: errMes,
    refetch: refMes,
  } = useAgendaMes(ano, mes);
  const {
    data: eventosAno,
    isLoading: loadAno,
    isError: errAno,
    refetch: refAno,
  } = useAgendaAno(ano);

  const eventos = modo === "mes" ? eventosMes : eventosAno;
  const isLoading = modo === "mes" ? loadMes : loadAno;
  const isError = modo === "mes" ? errMes : errAno;
  const refetch = modo === "mes" ? refMes : refAno;

  const proximos7 = React.useMemo(() => {
    const fonte = eventosAno ?? eventosMes ?? [];
    const hojeStr = hoje.toISOString().slice(0, 10);
    return [...fonte]
      .filter((e) => e.data >= hojeStr && e.status !== "pago")
      .sort((a, b) => a.data.localeCompare(b.data))
      .slice(0, 7);
  }, [eventosAno, eventosMes, hoje]);

  function trocarMes(delta: number) {
    let novoMes = mes + delta;
    let novoAno = ano;
    if (novoMes > 12) {
      novoMes = 1;
      novoAno += 1;
    }
    if (novoMes < 1) {
      novoMes = 12;
      novoAno -= 1;
    }
    setMes(novoMes);
    setAno(novoAno);
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Agenda
          </span>
          <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Calendário fiscal
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
            Tudo que vence: DAS, INSS, FGTS, DCTFWeb, eSocial. Customizado
            pelo perfil da sua empresa.
          </p>
        </div>
        <div className="flex items-center gap-1 p-1 rounded-md border" style={{ borderColor: "var(--color-line-2)" }}>
          <button
            type="button"
            onClick={() => setModo("mes")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors",
              modo === "mes"
                ? "bg-[var(--color-card-2)] text-[var(--color-txt)]"
                : "text-[var(--color-txt-2)] hover:text-[var(--color-txt)]"
            )}
          >
            <Calendar className="size-3.5" /> Mês
          </button>
          <button
            type="button"
            onClick={() => setModo("ano")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors",
              modo === "ano"
                ? "bg-[var(--color-card-2)] text-[var(--color-txt)]"
                : "text-[var(--color-txt-2)] hover:text-[var(--color-txt)]"
            )}
          >
            <List className="size-3.5" /> Lista anual
          </button>
        </div>
      </header>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        {modo === "mes" ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => trocarMes(-1)} aria-label="Mês anterior">
              <ChevronLeft className="size-4" />
            </Button>
            <h2 className="text-base font-bold text-[var(--color-txt)] min-w-[180px] text-center">
              {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}
            </h2>
            <Button variant="outline" onClick={() => trocarMes(1)} aria-label="Próximo mês">
              <ChevronRight className="size-4" />
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setAno(hoje.getFullYear());
                setMes(hoje.getMonth() + 1);
              }}
              className="text-xs"
            >
              Hoje
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setAno(ano - 1)} aria-label="Ano anterior">
              <ChevronLeft className="size-4" />
            </Button>
            <h2 className="mono text-lg font-bold text-[var(--color-txt)] min-w-[80px] text-center">
              {ano}
            </h2>
            <Button variant="outline" onClick={() => setAno(ano + 1)} aria-label="Próximo ano">
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}

        <div className="flex items-center gap-3 text-[10px] mono text-[var(--color-txt-2)] flex-wrap">
          <Legenda cor="var(--color-lime)" texto="Pago" />
          <Legenda cor="var(--color-amber)" texto="Pendente" />
          <Legenda cor="var(--color-red)" texto="Atrasado" />
          <Legenda cor="var(--color-blue)" texto="Informativo" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
        <div>
          {isLoading ? (
            <LoadingState titulo="Carregando agenda..." />
          ) : isError ? (
            <ErrorState onTentarNovamente={() => void refetch()} />
          ) : modo === "mes" ? (
            <Card className="overflow-hidden">
              <CalendarioMes ano={ano} mes={mes} eventos={eventos ?? []} hoje={hoje} />
            </Card>
          ) : (
            <ListaAnual eventos={eventos ?? []} />
          )}
        </div>

        <Card className="p-5 flex flex-col gap-3 self-start">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Próximos 7 vencimentos
            </span>
          </div>
          {proximos7.length === 0 ? (
            <EmptyState
              titulo="Nada pendente"
              descricao="Sem obrigações nas próximas semanas."
              className="py-8"
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {proximos7.map((e) => (
                <LinhaProximo key={e.id} evento={e} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2 rounded-full" style={{ background: cor }} />
      {texto}
    </span>
  );
}

function LinhaProximo({ evento }: { evento: EventoAgenda }) {
  const dias = Math.ceil(
    (new Date(evento.data).getTime() - Date.now()) / (24 * 60 * 60 * 1000)
  );
  return (
    <li
      className="rounded-md border p-2.5 flex items-start gap-2.5 text-sm"
      style={{
        background: "var(--color-card-2)",
        borderColor: "var(--color-line-2)",
        borderLeft: `3px solid ${COR_STATUS_AGENDA[evento.status]}`,
      }}
    >
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="font-semibold text-[var(--color-txt)] truncate">
          {evento.titulo}
        </span>
        <span className="text-[11px] text-[var(--color-txt-3)] mono">
          {formatarDataBR(evento.data)} ·{" "}
          {dias === 0 ? "hoje" : dias === 1 ? "amanhã" : `em ${dias}d`}
        </span>
        {evento.valor ? (
          <span className="mono text-xs text-[var(--color-txt-2)]">
            <Moeda valor={evento.valor} />
          </span>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-1">
        <StatusEventoAgendaPill status={evento.status} />
        {evento.rota ? (
          <Link
            href={evento.rota}
            className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-lime)] hover:underline"
          >
            Resolver →
          </Link>
        ) : null}
      </div>
    </li>
  );
}

function ListaAnual({ eventos }: { eventos: EventoAgenda[] }) {
  const porMes = React.useMemo(() => {
    const map = new Map<string, EventoAgenda[]>();
    for (const e of eventos) {
      const chave = e.data.slice(0, 7);
      const arr = map.get(chave) ?? [];
      arr.push(e);
      map.set(chave, arr);
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => a.data.localeCompare(b.data));
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [eventos]);

  if (porMes.length === 0) {
    return (
      <EmptyState
        titulo="Nenhum evento no ano"
        descricao="Selecione outro ano ou volte para a visão mensal."
      />
    );
  }

  return (
    <Card className="overflow-hidden">
      <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
        {porMes.map(([competencia, lista]) => (
          <li key={competencia} className="flex flex-col">
            <div
              className="px-5 py-2.5 bg-[var(--color-card-2)] text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono"
              style={{ borderColor: "var(--color-line)" }}
            >
              {formatarMesAnoBR(`${competencia}-01`)}
            </div>
            <ul
              className="divide-y"
              style={{ borderColor: "var(--color-line)" }}
            >
              {lista.map((e) => (
                <li
                  key={e.id}
                  className="px-5 py-2.5 flex items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors"
                >
                  <div
                    className="size-2 rounded-full shrink-0"
                    style={{ background: COR_STATUS_AGENDA[e.status] }}
                  />
                  <span className="mono text-xs font-bold text-[var(--color-txt)] w-20 shrink-0">
                    {formatarDataBR(e.data)}
                  </span>
                  <span className="text-sm text-[var(--color-txt)] flex-1 min-w-0 truncate">
                    {e.titulo}
                  </span>
                  {e.valor ? (
                    <span className="mono text-sm font-semibold text-[var(--color-txt)] shrink-0">
                      <Moeda valor={e.valor} />
                    </span>
                  ) : null}
                  <StatusEventoAgendaPill status={e.status} />
                  {e.rota ? (
                    <Link
                      href={e.rota}
                      className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-lime)] hover:underline shrink-0"
                    >
                      Abrir →
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </Card>
  );
}
