"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Calendar, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { CalendarioMes } from "@/components/agenda/calendario-mes";
import {
  COR_STATUS_AGENDA,
  StatusEventoAgendaPill,
} from "@/components/agenda/status-evento-pill";
import { useAgendaAno, useAgendaMes } from "@/hooks/use-agenda";
import { formatarDataBR, formatarMesAnoBR } from "@/lib/format/data";
import type { EventoAgenda } from "@/lib/schemas/agenda";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";
import { traduzirObrigacao } from "@/lib/traducao/obrigacoes";
import { classificarUrgencia } from "@/lib/urgencia";

// ─── helpers de tradução ─────────────────────────────────────────────────────

/**
 * Tenta traduzir o título de um evento para PT claro, devolvendo
 * { titulo PT, sigla técnica } ou { titulo original, null } como fallback.
 *
 * Estratégia: o título do evento contém a sigla (ex. "DAS Simples Nacional",
 * "Eventos eSocial"). Tentamos casar com o mapa de obrigações por token.
 */
function resolverTituloEvento(titulo: string): { pt: string; sigla: string | null } {
  // Tenta token exato primeiro
  const candidatos = ["PGDAS-D", "PGDAS_D", "DCTFWeb", "DCTF", "eSocial", "ESOCIAL",
    "DEFIS", "DAS", "FGTS", "INSS", "GFIP", "DASN-SIMEI", "REINF"];

  for (const token of candidatos) {
    if (titulo.toUpperCase().includes(token.toUpperCase())) {
      const entrada = traduzirObrigacao(token);
      if (entrada) {
        return { pt: entrada.titulo, sigla: entrada.termoTecnico };
      }
    }
  }
  // Sem correspondência: retorna título original (sem vazar sigla crua)
  return { pt: titulo, sigla: null };
}

// ─── página ──────────────────────────────────────────────────────────────────

export default function AgendaPage() {
  const hoje = React.useMemo(() => new Date(), []);
  const [ano, setAno] = React.useState(hoje.getFullYear());
  const [mes, setMes] = React.useState(hoje.getMonth() + 1);
  const [modo, setModo] = React.useState<"mes" | "ano">("mes");
  const reduced = useReducedMotion();

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
    if (novoMes > 12) { novoMes = 1; novoAno += 1; }
    if (novoMes < 1)  { novoMes = 12; novoAno -= 1; }
    setMes(novoMes);
    setAno(novoAno);
  }

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
        className="flex items-end justify-between gap-3 flex-wrap"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={itemVariants}>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block">
            Agenda
          </span>
          <h1 className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight">
            Calendário fiscal
          </h1>
          <p className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1">
            Tudo que vence — guias, declarações e obrigações trabalhistas — organizado para o seu perfil.
          </p>
        </motion.div>
        {/* toggle de modo — quadrados técnicos, não pílulas */}
        <motion.div
          variants={itemVariants}
          className="flex items-center gap-1 p-1 rounded-[var(--radius-sm)] border"
          style={{ borderColor: "var(--color-rule-2)" }}
        >
          <button
            type="button"
            onClick={() => setModo("mes")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 mono text-[10px] uppercase tracking-[0.12em] font-bold rounded-[var(--radius-sm)] transition-colors",
              modo === "mes"
                ? "bg-[var(--color-paper-2)] text-[var(--color-ink)]"
                : "text-[var(--color-ink-3)] hover:text-[var(--color-ink-2)]"
            )}
          >
            <Calendar className="size-3.5" /> Mês
          </button>
          <button
            type="button"
            onClick={() => setModo("ano")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 mono text-[10px] uppercase tracking-[0.12em] font-bold rounded-[var(--radius-sm)] transition-colors",
              modo === "ano"
                ? "bg-[var(--color-paper-2)] text-[var(--color-ink)]"
                : "text-[var(--color-ink-3)] hover:text-[var(--color-ink-2)]"
            )}
          >
            <List className="size-3.5" /> Anual
          </button>
        </motion.div>
      </motion.header>

      {/* ── controles de navegação + legenda ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {modo === "mes" ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => trocarMes(-1)} aria-label="Mês anterior">
              <ChevronLeft className="size-4" />
            </Button>
            <h2 className="mono text-sm font-bold text-[var(--color-ink)] min-w-[180px] text-center uppercase tracking-[0.1em]"
                style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}
            </h2>
            <Button variant="outline" size="sm" onClick={() => trocarMes(1)} aria-label="Próximo mês">
              <ChevronRight className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setAno(hoje.getFullYear());
                setMes(hoje.getMonth() + 1);
              }}
              className="mono text-[10px] uppercase tracking-[0.12em]"
            >
              Hoje
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setAno(ano - 1)} aria-label="Ano anterior">
              <ChevronLeft className="size-4" />
            </Button>
            <h2 className="mono text-lg font-bold text-[var(--color-ink)] min-w-[80px] text-center"
                style={{ fontVariantNumeric: "tabular-nums" }}>
              {ano}
            </h2>
            <Button variant="outline" size="sm" onClick={() => setAno(ano + 1)} aria-label="Próximo ano">
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}

        {/* legenda com fios técnicos, não bolinhas */}
        <div className="flex items-center gap-4 text-[10px] mono uppercase tracking-[0.1em] text-[var(--color-ink-3)] flex-wrap">
          <Legenda cor="var(--color-green)"  texto="Pago" />
          <Legenda cor="var(--color-ochre)"  texto="Pendente" />
          <Legenda cor="var(--color-danger)" texto="Atrasado" />
          <Legenda cor="var(--color-ink-2)"  texto="Info" />
        </div>
      </div>

      {/* ── grade: calendário + próximos ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
        <div>
          {isLoading ? (
            <LoadingState titulo="Carregando agenda..." />
          ) : isError ? (
            <ErrorState onTentarNovamente={() => void refetch()} />
          ) : modo === "mes" ? (
            <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
              <CalendarioMes ano={ano} mes={mes} eventos={eventos ?? []} hoje={hoje} />
            </Framed>
          ) : (
            <ListaAnual eventos={eventos ?? []} />
          )}
        </div>

        {/* Fig. 01 — próximos vencimentos */}
        <Framed marks={false} tone="rule" surface="card" padded={false} className="self-start">
          <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-2">
            <Fig n={1} titulo="Próximos vencimentos" size="sm" />
          </div>
          <Ruler />
          <div className="p-4">
            {proximos7.length === 0 ? (
              <EmptyState
                titulo="Nada pendente"
                descricao="Sem obrigações nas próximas semanas."
                className="py-6"
              />
            ) : (
              <ul className="flex flex-col gap-2">
                {proximos7.map((e) => (
                  <LinhaProximo key={e.id} evento={e} />
                ))}
              </ul>
            )}
          </div>
        </Framed>
      </div>
    </motion.div>
  );
}

function Legenda({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="w-3 h-[2px] rounded-[var(--radius-sm)]"
        style={{ background: cor }}
        aria-hidden
      />
      {texto}
    </span>
  );
}

function LinhaProximo({ evento }: { evento: EventoAgenda }) {
  const urg = classificarUrgencia(evento.data);
  const { pt: tituloPT, sigla } = resolverTituloEvento(evento.titulo);

  return (
    <li
      className="rounded-[var(--radius-md)] border p-2.5 flex items-start gap-2.5 text-sm"
      style={{
        background: "var(--color-paper-2)",
        borderColor: "var(--color-rule-2)",
        borderLeft: `2px solid ${COR_STATUS_AGENDA[evento.status]}`,
      }}
    >
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        {/* título em PT + sigla técnica em abbr mono */}
        <span className="font-semibold text-[var(--color-ink)] truncate text-xs">
          {tituloPT}
          {sigla ? (
            <>
              {" "}
              <abbr
                title={sigla}
                className="mono text-[10px] font-normal text-[var(--color-ink-3)] no-underline"
              >
                {sigla}
              </abbr>
            </>
          ) : null}
        </span>
        {/* urgência em 3 níveis */}
        <span className="text-[11px] mono" style={{ fontVariantNumeric: "tabular-nums" }}>
          <span style={{ color: "var(--color-ink-3)" }}>
            {formatarDataBR(evento.data)} ·{" "}
          </span>
          <span
            style={{
              color:
                urg.nivel === "danger"
                  ? "var(--color-danger)"
                  : urg.nivel === "ochre"
                    ? "var(--color-ochre)"
                    : "var(--color-ink-3)",
              fontWeight: urg.nivel !== "neutro" ? 700 : 400,
            }}
          >
            {urg.rotulo}
          </span>
        </span>
        {evento.valor ? (
          <span className="mono text-xs text-[var(--color-ink-2)]">
            <Moeda valor={evento.valor} />
          </span>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        {/* pill de urgência para eventos danger/ochre */}
        {urg.nivel !== "neutro" ? (
          <Pill tom={urg.pillTom}>{urg.rotulo}</Pill>
        ) : (
          <StatusEventoAgendaPill status={evento.status} />
        )}
        {evento.rota ? (
          <Link
            href={evento.rota}
            className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-green)] hover:underline"
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
    <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
      <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
        {porMes.map(([competencia, lista]) => (
          <li key={competencia} className="flex flex-col">
            <div
              className="px-5 py-2.5 bg-[var(--color-paper-2)] text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)] mono border-b"
              style={{ borderColor: "var(--color-rule)" }}
            >
              {formatarMesAnoBR(`${competencia}-01`)}
            </div>
            <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
              {lista.map((e) => {
                const { pt: tituloPT, sigla } = resolverTituloEvento(e.titulo);
                const urg = classificarUrgencia(e.data);
                return (
                  <li
                    key={e.id}
                    className="px-5 py-2.5 flex items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors"
                  >
                    <div
                      className="w-2 h-[2px] rounded-[var(--radius-sm)] shrink-0"
                      style={{ background: COR_STATUS_AGENDA[e.status] }}
                      aria-hidden
                    />
                    <span className="mono text-xs font-bold text-[var(--color-ink)] w-20 shrink-0"
                          style={{ fontVariantNumeric: "tabular-nums" }}>
                      {formatarDataBR(e.data)}
                    </span>
                    {/* título PT + sigla técnica */}
                    <span className="text-sm text-[var(--color-ink)] flex-1 min-w-0 truncate">
                      {tituloPT}
                      {sigla ? (
                        <>
                          {" "}
                          <abbr
                            title={sigla}
                            className="mono text-[10px] font-normal text-[var(--color-ink-3)] no-underline"
                          >
                            {sigla}
                          </abbr>
                        </>
                      ) : null}
                    </span>
                    {e.valor ? (
                      <span className="mono text-sm font-semibold text-[var(--color-ink)] shrink-0"
                            style={{ fontVariantNumeric: "tabular-nums" }}>
                        <Moeda valor={e.valor} />
                      </span>
                    ) : null}
                    {/* urgência visível na lista anual */}
                    {urg.nivel !== "neutro" ? (
                      <Pill tom={urg.pillTom}>{urg.rotulo}</Pill>
                    ) : (
                      <StatusEventoAgendaPill status={e.status} />
                    )}
                    {e.rota ? (
                      <Link
                        href={e.rota}
                        className="text-[10px] mono uppercase tracking-[0.14em] font-bold text-[var(--color-green)] hover:underline shrink-0"
                      >
                        Abrir →
                      </Link>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </Framed>
  );
}
