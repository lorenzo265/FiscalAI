"use client";

/**
 * Tela do CONSULTOR (advisor) — identidade Arkan Claro v2.
 *
 * Três leituras do módulo backend `advisor`, sem o usuário precisar procurar:
 *  - número-herói = pontos para revisar (alertas + oportunidades);
 *  - Oportunidades (sugestões de economia: Fator R, parcelamento…);
 *  - Alertas (anomalias = saltos atípicos numa apuração);
 *  - Resumo semanal (digest pronto para o WhatsApp) — gerar + enviar.
 *
 * Gates v2: 1 número-herói mono, ≤3 blocos acima da dobra, mono em todo dado,
 * verde só em saúde/ação, sem pílula/sombra, jargão traduzido (z-score/método
 * crus nunca aparecem — o backend já redige a `mensagem`).
 */
import * as React from "react";
import { motion } from "framer-motion";
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
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import {
  useAnomalias,
  useDispensarAnomalia,
  useSugestoes,
  useDigests,
  useGerarDigest,
  useEnviarDigest,
} from "@/hooks/use-advisor";
import type { Anomalia } from "@/lib/api/advisor";
import { ApiError } from "@/lib/http";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { useCountUp } from "@/lib/motion/use-count-up";

// ── tradução amigável (jargão nunca cru) ─────────────────────────────────────

const TIPO_TRIBUTO_LABEL: Record<string, string> = {
  das: "DAS (Simples Nacional)",
  irpj: "IRPJ",
  csll: "CSLL",
  pis: "PIS",
  cofins: "COFINS",
  iss: "ISS",
  icms: "ICMS",
};

function rotuloTributo(t: string): string {
  return TIPO_TRIBUTO_LABEL[t] ?? t.toUpperCase();
}

/** "2026-06-01" → "06/2026". */
function competenciaLabel(d: string): string {
  const [ano, mes] = d.split("-");
  return mes && ano ? `${mes}/${ano}` : d;
}

interface Tom {
  label: string;
  fg: string;
  bg: string;
}

const SEVERIDADE_ANOMALIA: Record<string, Tom> = {
  alta: { label: "Alta", fg: "var(--color-danger)", bg: "var(--color-danger-wash)" },
  media: { label: "Média", fg: "var(--color-ochre)", bg: "var(--color-ochre-wash)" },
  baixa: { label: "Baixa", fg: "var(--color-ink-2)", bg: "var(--color-paper-2)" },
};

const SEVERIDADE_SUGESTAO: Record<string, Tom> = {
  alta: { label: "Prioritária", fg: "var(--color-green)", bg: "var(--color-green-wash)" },
  media: { label: "Recomendada", fg: "var(--color-ochre)", bg: "var(--color-ochre-wash)" },
  informativa: { label: "Informativa", fg: "var(--color-ink-2)", bg: "var(--color-paper-2)" },
};

const STATUS_DIGEST: Record<string, Tom> = {
  preparado: { label: "Preparado", fg: "var(--color-ink-2)", bg: "var(--color-paper-2)" },
  enviado: { label: "Enviado", fg: "var(--color-green)", bg: "var(--color-green-wash)" },
  cancelado: { label: "Cancelado", fg: "var(--color-ink-2)", bg: "var(--color-paper-2)" },
  falhou: { label: "Falhou", fg: "var(--color-danger)", bg: "var(--color-danger-wash)" },
};

/** Fallback tipado (literal, não index access) para enum desconhecido. */
const TOM_FALLBACK: Tom = {
  label: "—",
  fg: "var(--color-ink-2)",
  bg: "var(--color-paper-2)",
};

function tomDigest(status: string): Tom {
  return STATUS_DIGEST[status] ?? TOM_FALLBACK;
}

function tomSugestao(severidade: string): Tom {
  return SEVERIDADE_SUGESTAO[severidade] ?? TOM_FALLBACK;
}

function tomAnomalia(severidade: string): Tom {
  return SEVERIDADE_ANOMALIA[severidade] ?? TOM_FALLBACK;
}

// ── tag técnica (não-pílula: radius 2px, mono, borda fina) ────────────────────

function Tag({ tom, children }: { tom: Tom; children: React.ReactNode }) {
  return (
    <span
      className="mono text-[10px] font-bold uppercase tracking-[0.12em] px-1.5 py-0.5 rounded-[2px] border shrink-0"
      style={{ color: tom.fg, borderColor: tom.fg, background: tom.bg }}
    >
      {children}
    </span>
  );
}

// ── tela ──────────────────────────────────────────────────────────────────────

export default function ConsultorPage() {
  const reduced = useReducedMotion();

  const anomaliasQ = useAnomalias();
  const sugestoesQ = useSugestoes();
  const digestsQ = useDigests();
  const dispensar = useDispensarAnomalia();
  const gerar = useGerarDigest();
  const enviar = useEnviarDigest();

  const [alvoDispensa, setAlvoDispensa] = React.useState<Anomalia | null>(null);
  const [motivo, setMotivo] = React.useState("");

  const anomalias = anomaliasQ.data ?? [];
  const sugestoes = sugestoesQ.data?.sugestoes ?? [];
  const digests = digestsQ.data?.digests ?? [];
  const ultimoDigest = digests[0] ?? null;

  const economiaTotal = sugestoes.reduce(
    (acc, s) => acc + (s.economiaAnualEstimada ? Number(s.economiaAnualEstimada) : 0),
    0
  );
  const pontos = anomalias.length + sugestoes.length;
  const heroNum = useCountUp(pontos, { format: Math.round });

  const carregandoTudo =
    anomaliasQ.isLoading && sugestoesQ.isLoading && digestsQ.isLoading;
  const erroTudo =
    anomaliasQ.isError && sugestoesQ.isError && digestsQ.isError;

  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;
  const pageReveal = reduced ? staticVariants : reveal;

  async function confirmarDispensa() {
    if (!alvoDispensa) return;
    try {
      await dispensar.mutateAsync({
        anomaliaId: alvoDispensa.id,
        motivo: motivo.trim(),
      });
      toast.success("Alerta dispensado", {
        description: "Ele sai da sua lista de pendências.",
      });
      setAlvoDispensa(null);
      setMotivo("");
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.mensagem : "Não foi possível dispensar agora.";
      toast.error("Falha ao dispensar", { description: msg });
    }
  }

  async function gerarResumo() {
    try {
      await gerar.mutateAsync({ forcar: false });
      toast.success("Resumo semanal gerado");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        toast.info("O resumo desta semana já existe", {
          description: "Veja abaixo o resumo mais recente.",
        });
        return;
      }
      const msg =
        e instanceof ApiError ? e.mensagem : "Não foi possível gerar o resumo.";
      toast.error("Falha ao gerar", { description: msg });
    }
  }

  async function enviarWhatsApp(digestId: string) {
    try {
      await enviar.mutateAsync(digestId);
      toast.success("Resumo enviado no WhatsApp");
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.mensagem : "Não foi possível enviar agora.";
      toast.error("Falha ao enviar", { description: msg });
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
      <motion.header variants={containerVariants} initial="hidden" animate="show">
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Módulo · Consultor
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Consultor fiscal
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
        >
          O que o sistema percebeu nos seus números — alertas de movimento
          atípico e oportunidades de economia, sem você precisar procurar.
        </motion.p>
      </motion.header>

      {erroTudo ? (
        <ErrorState
          titulo="Não foi possível falar com o consultor"
          onTentarNovamente={() => {
            void anomaliasQ.refetch();
            void sugestoesQ.refetch();
            void digestsQ.refetch();
          }}
        />
      ) : carregandoTudo ? (
        <LoadingState titulo="Consultando seus números..." />
      ) : (
        <>
          {/* ── número-herói ── */}
          <Framed
            marks={false}
            tone="rule"
            surface="card"
            className="flex flex-col sm:flex-row sm:items-end gap-4 sm:gap-6"
          >
            <div className="flex flex-col">
              <span
                className="mono text-[56px] md:text-[64px] font-bold leading-none text-[var(--color-ink)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {heroNum}
              </span>
              <span className="text-sm font-semibold text-[var(--color-ink)] mt-2">
                {pontos === 0
                  ? "Nada pendente"
                  : pontos === 1
                    ? "ponto para revisar"
                    : "pontos para revisar"}
              </span>
              <span className="text-xs text-[var(--color-ink-2)]">
                {pontos === 0
                  ? "Nenhuma anomalia ou oportunidade nesta competência."
                  : `${anomalias.length} ${anomalias.length === 1 ? "alerta" : "alertas"} · ${sugestoes.length} ${sugestoes.length === 1 ? "oportunidade" : "oportunidades"}`}
              </span>
            </div>

            {economiaTotal > 0 ? (
              <div className="flex flex-col sm:ml-auto sm:items-end">
                <Moeda
                  valor={economiaTotal}
                  className="text-xl font-bold text-[var(--color-green)]"
                />
                <span className="text-xs text-[var(--color-ink-2)]">
                  economia estimada por ano
                </span>
              </div>
            ) : null}
          </Framed>

          {/* ── Oportunidades ── */}
          {sugestoesQ.isError ? (
            <ErrorState
              titulo="Não foi possível carregar as oportunidades"
              onTentarNovamente={() => void sugestoesQ.refetch()}
            />
          ) : sugestoes.length === 0 ? (
            <Framed marks={false} surface="card">
              <Fig n={1} titulo="Oportunidades" size="sm" />
              <p className="text-sm text-[var(--color-ink-2)] mt-3 leading-relaxed">
                Nenhuma oportunidade de economia mapeada nesta competência.
                Quando houver (enquadramento no Fator R, parcelamento de DAS),
                aparece aqui.
              </p>
            </Framed>
          ) : (
            <Framed
              marks={false}
              tone="ink"
              surface="card"
              padded={false}
              className="overflow-hidden"
            >
              <div className="px-5 pt-4 pb-2">
                <Fig n={1} titulo={`Oportunidades (${sugestoes.length})`} size="sm" />
              </div>
              <Ruler />
              <ul>
                {sugestoes.map((s) => {
                  const tom = tomSugestao(s.severidade);
                  const economia = s.economiaAnualEstimada
                    ? Number(s.economiaAnualEstimada)
                    : 0;
                  return (
                    <li
                      key={s.codigo}
                      className="px-5 py-4 flex flex-col gap-2 border-b last:border-b-0"
                      style={{ borderColor: "var(--color-rule)" }}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-[var(--color-ink)]">
                          {s.titulo}
                        </span>
                        <Tag tom={tom}>{tom.label}</Tag>
                        {economia > 0 ? (
                          <span
                            className="ml-auto mono text-sm font-bold text-[var(--color-green)]"
                            style={{ fontVariantNumeric: "tabular-nums" }}
                          >
                            <Moeda valor={economia} className="text-[var(--color-green)]" />
                            /ano
                          </span>
                        ) : null}
                      </div>
                      <p className="text-[13px] text-[var(--color-ink-2)] leading-relaxed">
                        {s.descricao}
                      </p>
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <span className="mono text-[11px] text-[var(--color-ink-2)]">
                          {s.fonteNorma}
                        </span>
                        <span className="text-[11px] text-[var(--color-ink-2)]">
                          · {s.observacaoEstimativa}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Framed>
          )}

          {/* ── Alertas ── */}
          {anomaliasQ.isError ? (
            <ErrorState
              titulo="Não foi possível carregar os alertas"
              onTentarNovamente={() => void anomaliasQ.refetch()}
            />
          ) : anomalias.length === 0 ? (
            <Framed marks={false} surface="card">
              <Fig n={2} titulo="Alertas" size="sm" />
              <p className="text-sm text-[var(--color-ink-2)] mt-3 leading-relaxed">
                Nenhum movimento atípico nas suas apurações. Quando um imposto
                fugir do padrão dos últimos meses, o alerta aparece aqui.
              </p>
            </Framed>
          ) : (
            <Framed
              marks={false}
              tone="ink"
              surface="card"
              padded={false}
              className="overflow-hidden"
            >
              <div className="px-5 pt-4 pb-2">
                <Fig n={2} titulo={`Alertas (${anomalias.length})`} size="sm" />
              </div>
              <Ruler />
              <ul>
                {anomalias.map((a) => {
                  const tom = tomAnomalia(a.severidade);
                  return (
                    <li
                      key={a.id}
                      className="px-5 py-4 flex flex-col gap-2 border-b last:border-b-0"
                      style={{ borderColor: "var(--color-rule)" }}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="mono text-sm font-bold text-[var(--color-ink)]">
                          {rotuloTributo(a.tipo)}
                        </span>
                        <span
                          className="mono text-[11px] text-[var(--color-ink-2)]"
                          style={{ fontVariantNumeric: "tabular-nums" }}
                        >
                          {competenciaLabel(a.competencia)}
                        </span>
                        <Tag tom={tom}>{tom.label}</Tag>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="ml-auto"
                          onClick={() => {
                            setAlvoDispensa(a);
                            setMotivo("");
                          }}
                        >
                          Dispensar
                        </Button>
                      </div>
                      <p className="text-[13px] text-[var(--color-ink)] leading-relaxed">
                        {a.mensagem}
                      </p>
                      <div className="flex items-center gap-4 flex-wrap text-[11px]">
                        <span className="text-[var(--color-ink-2)]">
                          observado{" "}
                          <span className="mono font-bold text-[var(--color-ink)]">
                            <Moeda valor={Number(a.valorObservado)} />
                          </span>
                        </span>
                        <span className="text-[var(--color-ink-2)]">
                          esperado{" "}
                          <span className="mono font-bold text-[var(--color-ink)]">
                            <Moeda valor={Number(a.valorEsperado)} />
                          </span>
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Framed>
          )}

          {/* ── Resumo semanal (digest) ── */}
          <Framed
            marks={false}
            tone="ink"
            surface="card"
            padded={false}
            className="overflow-hidden"
          >
            <div className="px-5 pt-4 pb-2 flex items-center gap-3">
              <Fig n={3} titulo="Resumo semanal" size="sm" />
              <Button
                size="sm"
                className="ml-auto"
                disabled={gerar.isPending}
                onClick={gerarResumo}
              >
                {gerar.isPending ? "Gerando..." : "Gerar resumo"}
              </Button>
            </div>
            <Ruler />
            <div className="p-5 flex flex-col gap-4">
              {digestsQ.isError ? (
                <ErrorState
                  titulo="Não foi possível carregar os resumos"
                  onTentarNovamente={() => void digestsQ.refetch()}
                />
              ) : ultimoDigest ? (
                <>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="mono text-[11px] font-bold text-[var(--color-ink)]"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {ultimoDigest.semanaIso}
                    </span>
                    <Tag tom={tomDigest(ultimoDigest.status)}>
                      {tomDigest(ultimoDigest.status).label}
                    </Tag>
                  </div>
                  <p className="text-sm text-[var(--color-ink)] leading-relaxed whitespace-pre-line">
                    {ultimoDigest.textoRedigido}
                  </p>
                  {ultimoDigest.status === "preparado" ? (
                    <div>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={enviar.isPending}
                        onClick={() => enviarWhatsApp(ultimoDigest.id)}
                      >
                        {enviar.isPending ? "Enviando..." : "Enviar no WhatsApp"}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
                  Nenhum resumo gerado ainda. Toque em “Gerar resumo” para criar
                  o panorama da semana — apuração, alertas e oportunidades num
                  texto pronto para o WhatsApp.
                </p>
              )}

              {digests.length > 1 ? (
                <div
                  className="flex flex-col gap-1.5 pt-3 border-t"
                  style={{ borderColor: "var(--color-rule)" }}
                >
                  <span className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-ink-2)] font-bold">
                    Anteriores
                  </span>
                  {digests.slice(1, 6).map((d) => (
                    <div key={d.id} className="flex items-center gap-2 text-[12px]">
                      <span
                        className="mono text-[var(--color-ink)]"
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {d.semanaIso}
                      </span>
                      <Tag tom={tomDigest(d.status)}>{tomDigest(d.status).label}</Tag>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </Framed>
        </>
      )}

      {/* ── Dialog: dispensar alerta ── */}
      <Dialog
        open={!!alvoDispensa}
        onOpenChange={(v) => {
          if (!v) {
            setAlvoDispensa(null);
            setMotivo("");
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Dispensar alerta</DialogTitle>
            <DialogDescription>
              {alvoDispensa
                ? `${rotuloTributo(alvoDispensa.tipo)} · ${competenciaLabel(alvoDispensa.competencia)}. Conte por que esse movimento é esperado — fica registrado.`
                : ""}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-1.5">
            <textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="Ex.: compra sazonal de estoque para o fim de ano."
              className="w-full rounded-[var(--radius-md)] border p-3 text-sm bg-[var(--color-paper)] text-[var(--color-ink)] resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/35"
              style={{ borderColor: "var(--color-rule-2)" }}
            />
            <span
              className="mono text-[10px] text-[var(--color-ink-2)] self-end"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {motivo.trim().length}/500 · mínimo 3
            </span>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setAlvoDispensa(null);
                setMotivo("");
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={dispensar.isPending || motivo.trim().length < 3}
              onClick={confirmarDispensa}
            >
              {dispensar.isPending ? "Dispensando..." : "Dispensar alerta"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
