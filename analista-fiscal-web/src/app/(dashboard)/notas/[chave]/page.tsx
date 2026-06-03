"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Ban,
  Building2,
  CalendarClock,
  Download,
  FileText,
  PenLine,
  User,
} from "lucide-react";
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
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import {
  ManifestoPill,
  StatusNotaPill,
  TipoNotaPill,
} from "@/components/notas/status-pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { BlueprintSchematic } from "@/components/blueprint/blueprint-schematic";
import { Carimbo } from "@/components/blueprint/carimbo";
import {
  useCancelarNota,
  useEmitirCartaCorrecao,
  useNota,
} from "@/hooks/use-notas";
import { baixarDANFE, baixarXml } from "@/lib/notas/downloads";
import { formatarChave } from "@/lib/notas/chave";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR, formatarDataHoraBR } from "@/lib/format/data";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

/* Mapa de CFOP frequentes → PT claro (invariante §7: nunca expor código cru) */
const CFOP_LABELS: Record<string, string> = {
  "5101": "Venda de produção própria",
  "5102": "Venda de mercadoria",
  "5103": "Venda de produção para fora do estado",
  "5104": "Venda de mercadoria para fora do estado",
  "5405": "Venda de mercadoria sujeita a substituição tributária",
  "6101": "Venda interestadual de produção própria",
  "6102": "Venda interestadual de mercadoria",
  "5933": "Prestação de serviço tributado pelo ISSQN",
  "5356": "Venda de serviço de comunicação",
  "1101": "Compra de produção própria do fornecedor",
  "1102": "Compra de mercadoria para industrialização",
  "1202": "Devolução de venda de produção própria",
  "2101": "Compra interestadual de produção própria",
  "2102": "Compra interestadual de mercadoria",
};

const CST_LABELS: Record<string, string> = {
  "00": "Tributada integralmente",
  "10": "Tributada com cobrança de ICMS-ST",
  "20": "Com redução de base de cálculo",
  "40": "Isenta",
  "41": "Não tributada",
  "50": "Suspensão",
  "60": "Cobrado anteriormente por substituição tributária",
  "400": "Simples Nacional — tributada",
  "500": "Simples Nacional — ST",
};

const NCM_LABELS: Record<string, string> = {
  "00000000": "Mercadoria geral",
};

function traduzirCFOP(cfop: string): string {
  return CFOP_LABELS[cfop] ?? `Operação ${cfop}`;
}
function traduzirCST(cst: string): string {
  return CST_LABELS[cst] ?? `Tributação ${cst}`;
}
function traduzirNCM(ncm: string): string {
  return NCM_LABELS[ncm] ?? "Mercadoria / serviço";
}

const PRAZO_CANCELAMENTO_DIAS = 7;

export default function NotaDetalhePage() {
  const params = useParams<{ chave: string }>();
  const router = useRouter();
  const reduced = useReducedMotion();
  const chave = params?.chave ?? null;
  const { data: nota, isLoading, isError, refetch } = useNota(chave);
  const cancelar = useCancelarNota();
  const cce = useEmitirCartaCorrecao();

  const [cancelAberto, setCancelAberto] = React.useState(false);
  const [motivo, setMotivo] = React.useState("");
  const [cceAberto, setCceAberto] = React.useState(false);
  const [textoCce, setTextoCce] = React.useState("");

  /* ── estados de carregamento ── */
  if (isLoading) {
    return <LoadingState titulo="Carregando nota..." />;
  }
  if (isError) {
    return <ErrorState onTentarNovamente={() => void refetch()} />;
  }
  if (!nota) {
    return (
      <EmptyState
        titulo="Nota não encontrada"
        descricao="Verifique se a chave de acesso está correta ou volte à lista de notas."
        icone={FileText}
        acao={
          <Button asChild variant="outline" size="sm">
            <Link href="/notas">
              <ArrowLeft className="size-3.5" /> Voltar para a lista
            </Link>
          </Button>
        }
      />
    );
  }

  const podeCancelar =
    nota.status === "autorizada" &&
    Date.now() - new Date(nota.emitidaEm).getTime() <
      PRAZO_CANCELAMENTO_DIAS * 24 * 60 * 60 * 1000;

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
      <motion.div
        className="flex items-start justify-between gap-3 flex-wrap"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <div className="flex flex-col gap-1">
          <motion.div variants={itemVariants}>
            <Link
              href="/notas"
              className="text-[12px] text-[var(--color-ink-3)] hover:text-[var(--color-ink)] transition-colors flex items-center gap-1"
            >
              <ArrowLeft className="size-3" /> Todas as notas
            </Link>
          </motion.div>
          <motion.div variants={itemVariants} className="flex items-baseline gap-3 flex-wrap">
            <h1 className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-none">
              NF-e{" "}
              <span
                className="mono font-bold"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                nº {nota.numero}
              </span>
            </h1>
            <div className="flex items-center gap-2 flex-wrap">
              <TipoNotaPill tipo={nota.tipo} />
              <StatusNotaPill status={nota.status} />
              {nota.tipo === "entrada" && nota.manifesto ? (
                <ManifestoPill manifesto={nota.manifesto} />
              ) : null}
            </div>
          </motion.div>
        </div>

        <motion.div variants={itemVariants} className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => baixarDANFE(nota)}>
            <FileText className="size-3.5" /> Baixar DANFE
          </Button>
          <Button variant="outline" size="sm" onClick={() => baixarXml(nota)}>
            <Download className="size-3.5" /> Baixar XML
          </Button>
          {podeCancelar ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setCancelAberto(true)}
            >
              <Ban className="size-3.5" /> Cancelar nota
            </Button>
          ) : null}
          {nota.status === "autorizada" ? (
            <Button variant="ghost" size="sm" onClick={() => setCceAberto(true)}>
              <PenLine className="size-3.5" /> Carta de correção
            </Button>
          ) : null}
        </motion.div>
      </motion.div>

      {/* ── grade principal ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        {/* coluna esquerda — documento */}
        <Framed marks tone="ink" surface="card" padded={false} className="flex flex-col">
          {/* Fig. 01 — Identificação */}
          <div className="px-5 pt-5 pb-4 flex flex-col gap-3">
            <Fig n={1} titulo="Identificação" />
            <div
              className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-2"
              style={{
                background: "var(--color-paper-2)",
                borderColor: "var(--color-rule-2)",
              }}
            >
              <span className="text-[10px] uppercase tracking-[0.18em] font-bold text-[var(--color-ink-3)] mono">
                Chave de acesso
              </span>
              <span
                className="mono text-[12px] md:text-sm text-[var(--color-ink)] break-all leading-relaxed"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarChave(nota.chave)}
              </span>
              {nota.protocoloAutorizacao ? (
                <span
                  className="mono text-[11px] text-[var(--color-ink-3)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  Protocolo: {nota.protocoloAutorizacao}
                </span>
              ) : null}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <BlocoEntidade
                titulo={nota.tipo === "saida" ? "Emitente" : "Remetente"}
                icon={Building2}
                nome={nota.razaoEmitente}
                documento={formatarCNPJ(nota.cnpjEmitente)}
              />
              <BlocoEntidade
                titulo={
                  nota.tipo === "saida"
                    ? "Destinatário"
                    : "Destinatário (você)"
                }
                icon={
                  nota.contraparte.tipo === "pj" ? Building2 : User
                }
                nome={nota.contraparte.nome}
                documento={
                  nota.contraparte.tipo === "pj"
                    ? formatarCNPJ(nota.contraparte.documento)
                    : formatarCPF(nota.contraparte.documento)
                }
                endereco={nota.contraparte.endereco}
              />
            </div>
          </div>

          <Ruler />

          {/* Fig. 02 — Itens */}
          <div className="px-5 py-4 flex flex-col gap-3">
            <Fig n={2} titulo={`Itens (${nota.itens.length})`} />
            <div
              className="overflow-x-auto rounded-[var(--radius-md)] border"
              style={{ borderColor: "var(--color-rule-2)" }}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr
                    className="text-left text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono border-b"
                    style={{ borderColor: "var(--color-rule-2)" }}
                  >
                    <th className="px-3 py-2 font-bold">Descrição</th>
                    <th className="px-3 py-2 font-bold">Operação</th>
                    <th className="px-3 py-2 text-right font-bold">Qtd</th>
                    <th className="px-3 py-2 text-right font-bold">Vl.unit.</th>
                    <th className="px-3 py-2 text-right font-bold">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {nota.itens.map((it) => (
                    <tr
                      key={it.id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: "var(--color-rule)" }}
                    >
                      <td className="px-3 py-2.5 align-top">
                        <span className="text-[var(--color-ink)] block font-medium">
                          {it.descricao}
                        </span>
                        {/* NCM traduzido — código em mono como detalhe */}
                        <span className="text-[11px] text-[var(--color-ink-3)] mono leading-snug">
                          {traduzirNCM(it.ncm)}{" "}
                          <abbr
                            title={`NCM ${it.ncm}`}
                            className="no-underline opacity-60"
                          >
                            ·{" "}
                            <span style={{ fontVariantNumeric: "tabular-nums" }}>
                              {it.ncm}
                            </span>
                          </abbr>
                        </span>
                        {/* CST/CSOSN traduzido */}
                        <span className="text-[10px] text-[var(--color-ink-3)] mono leading-snug">
                          {traduzirCST(it.cstCsosn)}{" "}
                          <abbr
                            title={`CST/CSOSN ${it.cstCsosn}`}
                            className="no-underline opacity-50"
                          >
                            ·{" "}
                            <span style={{ fontVariantNumeric: "tabular-nums" }}>
                              {it.cstCsosn}
                            </span>
                          </abbr>
                        </span>
                      </td>
                      {/* CFOP traduzido — código em mono como detalhe secundário */}
                      <td className="px-3 py-2.5 align-top">
                        <span className="text-[var(--color-ink-2)] text-[12px] block leading-snug">
                          {traduzirCFOP(it.cfop)}
                        </span>
                        <span
                          className="mono text-[10px] text-[var(--color-ink-3)] opacity-70"
                          style={{ fontVariantNumeric: "tabular-nums" }}
                        >
                          CFOP {it.cfop}
                        </span>
                      </td>
                      <td
                        className="px-3 py-2.5 align-top mono text-[var(--color-ink-2)] text-right text-[12px]"
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {it.quantidade.toString().replace(".", ",")}{" "}
                        {it.unidade}
                      </td>
                      <td
                        className="px-3 py-2.5 align-top mono text-[var(--color-ink-2)] text-right text-[12px]"
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {formatarMoeda(it.valorUnitario)}
                      </td>
                      <td
                        className="px-3 py-2.5 align-top mono text-[var(--color-ink)] text-right text-[13px] font-bold"
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {formatarMoeda(it.valorTotal)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Fig. 03 — Informações adicionais (condicional) */}
          {nota.observacao ? (
            <>
              <Ruler />
              <div className="px-5 py-4 flex flex-col gap-2">
                <Fig n={3} titulo="Informações adicionais" />
                <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
                  {nota.observacao}
                </p>
              </div>
            </>
          ) : null}

          {/* Cartas de correção (condicional) */}
          {nota.cartasCorrecao && nota.cartasCorrecao.length > 0 ? (
            <>
              <Ruler />
              <div className="px-5 py-4 flex flex-col gap-3">
                <Fig
                  n={nota.observacao ? 4 : 3}
                  titulo="Cartas de correção (CC-e)"
                />
                <ul className="flex flex-col gap-2">
                  {nota.cartasCorrecao.map((c) => (
                    <li
                      key={c.sequencia}
                      className="rounded-[var(--radius-md)] border p-3 text-sm"
                      style={{
                        background: "var(--color-paper-2)",
                        borderColor: "var(--color-rule-2)",
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <Pill tom="info">CC-e #{c.sequencia}</Pill>
                        <span
                          className="text-[11px] text-[var(--color-ink-3)] mono"
                          style={{ fontVariantNumeric: "tabular-nums" }}
                        >
                          {formatarDataHoraBR(c.emitidaEm)}
                        </span>
                      </div>
                      <p className="text-[var(--color-ink)] mt-2 leading-relaxed">
                        {c.texto}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          ) : null}

          {/* Estado cancelada — Carimbo substitui o bloco vermelho */}
          {nota.status === "cancelada" && nota.canceladaEm ? (
            <>
              <Ruler />
              <div className="px-5 py-4 flex items-center gap-4">
                <Carimbo tom="danger" inView sub={formatarDataBR(nota.canceladaEm)}>
                  Cancelada
                </Carimbo>
                <span className="text-sm text-[var(--color-ink-2)]">
                  {nota.motivoCancelamento ?? "sem motivo registrado"}
                </span>
              </div>
            </>
          ) : null}

          <div className="pb-5" />
        </Framed>

        {/* coluna direita */}
        <div className="flex flex-col gap-4">
          {/* BlueprintSchematic — signature da tela [chave] */}
          <Framed marks={false} tone="rule" surface="paper-2" padded className="flex flex-col items-center gap-3">
            <BlueprintSchematic width={160} figure="nota" />
            {nota.status === "autorizada" ? (
              <Carimbo tom="green" inView sub={formatarDataBR(nota.emitidaEm)}>
                Autorizada
              </Carimbo>
            ) : nota.status === "cancelada" ? (
              <Carimbo tom="danger" inView>
                Cancelada
              </Carimbo>
            ) : (
              <Carimbo tom="ink" inView>
                {nota.status === "emitida" ? "Em análise" : nota.status}
              </Carimbo>
            )}
          </Framed>

          {/* Totais */}
          <Framed marks tone="rule" surface="card">
            <div className="flex flex-col gap-3">
              <Fig n={4} titulo="Totais" />
              <Ruler />
              <div className="flex flex-col gap-1.5 pt-1">
                <Linha label="Produtos / serviços" valor={nota.totais.produtos} />
                {nota.totais.icms > 0 ? (
                  <Linha label="ICMS" valor={nota.totais.icms} sub />
                ) : null}
                {nota.totais.iss > 0 ? (
                  <Linha label="ISS" valor={nota.totais.iss} sub />
                ) : null}
                {nota.totais.pis > 0 ? (
                  <Linha label="PIS" valor={nota.totais.pis} sub />
                ) : null}
                {nota.totais.cofins > 0 ? (
                  <Linha label="Cofins" valor={nota.totais.cofins} sub />
                ) : null}
              </div>
              <div
                className="border-t pt-3 flex items-baseline justify-between"
                style={{ borderColor: "var(--color-rule)" }}
              >
                <span className="text-[10px] uppercase tracking-[0.18em] font-bold text-[var(--color-ink-3)] mono">
                  Total da nota
                </span>
                <span
                  className="mono text-2xl font-extrabold text-[var(--color-ink)]"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  <Moeda valor={nota.totais.valorNota} />
                </span>
              </div>
            </div>
          </Framed>

          {/* Datas / pagamento */}
          <Framed marks={false} tone="rule" surface="paper-2">
            <div className="flex flex-col gap-2">
              <div className="flex items-start gap-2">
                <CalendarClock
                  className="size-4 text-[var(--color-ink-3)] mt-0.5 shrink-0"
                  aria-hidden
                />
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
                    Emissão
                  </span>
                  <span className="text-sm text-[var(--color-ink)]">
                    {formatarDataHoraBR(nota.emitidaEm)}
                  </span>
                  {nota.pagamento ? (
                    <span className="text-[11px] text-[var(--color-ink-3)] mt-1">
                      {nota.pagamento.forma.replace("_", " ")} · vence{" "}
                      {nota.pagamento.vencimento
                        ? formatarDataBR(nota.pagamento.vencimento)
                        : "—"}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          </Framed>
        </div>
      </div>

      {/* ── Dialog cancelar ── */}
      <Dialog open={cancelAberto} onOpenChange={setCancelAberto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancelar NF-e {nota.numero}?</DialogTitle>
            <DialogDescription>
              O cancelamento envia o evento à SEFAZ. Após cancelada, a nota não
              pode ser reativada.
            </DialogDescription>
          </DialogHeader>
          <textarea
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Motivo do cancelamento (mínimo 15 caracteres)"
            rows={3}
            className="rounded-[var(--radius-md)] border bg-[var(--color-paper-2)] border-[var(--color-rule-2)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-ink-3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/30 resize-none w-full"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCancelAberto(false)}>
              Voltar
            </Button>
            <Button
              variant="destructive"
              disabled={motivo.trim().length < 15 || cancelar.isPending}
              onClick={async () => {
                await cancelar.mutateAsync({
                  chave: nota.chave,
                  motivo: motivo.trim(),
                });
                setCancelAberto(false);
                setMotivo("");
                toast.success("Nota cancelada", {
                  description: `NF-e ${nota.numero} marcada como cancelada.`,
                });
                router.refresh();
              }}
            >
              <Ban className="size-3.5" />
              Confirmar cancelamento
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog CC-e ── */}
      <Dialog open={cceAberto} onOpenChange={setCceAberto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Carta de correção eletrônica</DialogTitle>
            <DialogDescription>
              Use para corrigir informações da nota que não impactam valores ou
              destinatário.
            </DialogDescription>
          </DialogHeader>
          <textarea
            value={textoCce}
            onChange={(e) => setTextoCce(e.target.value)}
            placeholder="Descreva a correção..."
            rows={4}
            className="rounded-[var(--radius-md)] border bg-[var(--color-paper-2)] border-[var(--color-rule-2)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-ink-3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-green)]/30 resize-none w-full"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCceAberto(false)}>
              Voltar
            </Button>
            <Button
              disabled={textoCce.trim().length < 15 || cce.isPending}
              onClick={async () => {
                await cce.mutateAsync({
                  chave: nota.chave,
                  texto: textoCce.trim(),
                });
                setCceAberto(false);
                setTextoCce("");
                toast.success("Carta de correção enviada");
              }}
            >
              <PenLine className="size-3.5" />
              Emitir CC-e
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

/* ── sub-componentes ── */

function BlocoEntidade({
  titulo,
  icon: Icon,
  nome,
  documento,
  endereco,
}: {
  titulo: string;
  icon: typeof Building2;
  nome: string;
  documento: string;
  endereco?: {
    logradouro: string;
    numero: string;
    municipio: string;
    uf: string;
  };
}) {
  return (
    <div
      className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-2"
      style={{
        background: "var(--color-paper-2)",
        borderColor: "var(--color-rule-2)",
      }}
    >
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-[var(--color-ink-3)]" aria-hidden />
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
          {titulo}
        </span>
      </div>
      <span className="font-serif text-base text-[var(--color-ink)] leading-tight">
        {nome}
      </span>
      <span
        className="mono text-xs text-[var(--color-ink-2)]"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {documento}
      </span>
      {endereco ? (
        <span className="text-[11px] text-[var(--color-ink-3)] leading-snug">
          {endereco.logradouro}, {endereco.numero} · {endereco.municipio}/
          {endereco.uf}
        </span>
      ) : null}
    </div>
  );
}

function Linha({
  label,
  valor,
  sub,
}: {
  label: string;
  valor: number;
  sub?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span
        className={
          sub
            ? "text-[11px] text-[var(--color-ink-3)]"
            : "text-sm text-[var(--color-ink-2)]"
        }
      >
        {label}
      </span>
      <span
        className={
          sub
            ? "mono text-[11px] text-[var(--color-ink-3)]"
            : "mono text-sm text-[var(--color-ink)]"
        }
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}
