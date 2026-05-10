"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
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
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import {
  ManifestoPill,
  StatusNotaPill,
  TipoNotaPill,
} from "@/components/notas/status-pill";
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

const PRAZO_CANCELAMENTO_DIAS = 7;

export default function NotaDetalhePage() {
  const params = useParams<{ chave: string }>();
  const router = useRouter();
  const chave = params?.chave ?? null;
  const { data: nota, isLoading, isError, refetch } = useNota(chave);
  const cancelar = useCancelarNota();
  const cce = useEmitirCartaCorrecao();

  const [cancelAberto, setCancelAberto] = React.useState(false);
  const [motivo, setMotivo] = React.useState("");
  const [cceAberto, setCceAberto] = React.useState(false);
  const [textoCce, setTextoCce] = React.useState("");

  if (isLoading) {
    return <LoadingState titulo="Carregando nota..." />;
  }
  if (isError) {
    return <ErrorState onTentarNovamente={() => void refetch()} />;
  }
  if (!nota) {
    return (
      <div className="flex flex-col gap-3 items-start">
        <p className="text-sm text-[var(--color-txt-2)]">
          Nota não encontrada com essa chave.
        </p>
        <Button asChild variant="outline">
          <Link href="/notas">
            <ArrowLeft className="size-3.5" /> Voltar para a lista
          </Link>
        </Button>
      </div>
    );
  }

  const podeCancelar =
    nota.status === "autorizada" &&
    Date.now() - new Date(nota.emitidaEm).getTime() <
      PRAZO_CANCELAMENTO_DIAS * 24 * 60 * 60 * 1000;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <Link
            href="/notas"
            className="text-[12px] text-[var(--color-txt-3)] hover:text-[var(--color-txt)] transition-colors flex items-center gap-1"
          >
            <ArrowLeft className="size-3" /> Voltar para todas as notas
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
              NF-e nº{" "}
              <span className="mono">{nota.numero}</span>
            </h1>
            <TipoNotaPill tipo={nota.tipo} />
            <StatusNotaPill status={nota.status} />
            {nota.tipo === "entrada" && nota.manifesto ? (
              <ManifestoPill manifesto={nota.manifesto} />
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => baixarDANFE(nota)}>
            <FileText className="size-3.5" /> Baixar DANFE
          </Button>
          <Button variant="outline" onClick={() => baixarXml(nota)}>
            <Download className="size-3.5" /> Baixar XML
          </Button>
          {podeCancelar ? (
            <Button
              variant="destructive"
              onClick={() => setCancelAberto(true)}
            >
              <Ban className="size-3.5" /> Cancelar nota
            </Button>
          ) : null}
          {nota.status === "autorizada" ? (
            <Button variant="ghost" onClick={() => setCceAberto(true)}>
              <PenLine className="size-3.5" /> Carta de correção
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        <Card className="p-6 flex flex-col gap-5">
          <div
            className="rounded-md border p-4 flex flex-col gap-2"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
              Chave de acesso
            </span>
            <span className="mono text-[12px] md:text-sm text-[var(--color-txt)] break-all leading-relaxed">
              {formatarChave(nota.chave)}
            </span>
            {nota.protocoloAutorizacao ? (
              <span className="mono text-[11px] text-[var(--color-txt-3)]">
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
              titulo={nota.tipo === "saida" ? "Destinatário" : "Destinatário (você)"}
              icon={nota.contraparte.tipo === "pj" ? Building2 : User}
              nome={nota.contraparte.nome}
              documento={
                nota.contraparte.tipo === "pj"
                  ? formatarCNPJ(nota.contraparte.documento)
                  : formatarCPF(nota.contraparte.documento)
              }
              endereco={nota.contraparte.endereco}
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
              Itens ({nota.itens.length})
            </span>
            <div className="overflow-x-auto rounded-md border" style={{ borderColor: "var(--color-line-2)" }}>
              <table className="w-full text-sm">
                <thead>
                  <tr
                    className="text-left text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono border-b"
                    style={{ borderColor: "var(--color-line-2)" }}
                  >
                    <th className="px-3 py-2">Descrição</th>
                    <th className="px-3 py-2">NCM</th>
                    <th className="px-3 py-2">CFOP</th>
                    <th className="px-3 py-2 text-right">Qtd</th>
                    <th className="px-3 py-2 text-right">Vl.unit</th>
                    <th className="px-3 py-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {nota.itens.map((it) => (
                    <tr
                      key={it.id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: "var(--color-line)" }}
                    >
                      <td className="px-3 py-2 align-top">
                        <span className="text-[var(--color-txt)] block">
                          {it.descricao}
                        </span>
                        <span className="text-[11px] text-[var(--color-txt-3)] mono">
                          CST/CSOSN {it.cstCsosn}
                        </span>
                      </td>
                      <td className="px-3 py-2 align-top mono text-[var(--color-txt-2)]">
                        {it.ncm}
                      </td>
                      <td className="px-3 py-2 align-top mono text-[var(--color-txt-2)]">
                        {it.cfop}
                      </td>
                      <td className="px-3 py-2 align-top mono text-[var(--color-txt-2)] text-right">
                        {it.quantidade.toString().replace(".", ",")} {it.unidade}
                      </td>
                      <td className="px-3 py-2 align-top mono text-[var(--color-txt-2)] text-right">
                        {formatarMoeda(it.valorUnitario)}
                      </td>
                      <td className="px-3 py-2 align-top mono text-[var(--color-txt)] text-right font-bold">
                        {formatarMoeda(it.valorTotal)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {nota.observacao ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
                Informações adicionais
              </span>
              <p className="text-sm text-[var(--color-txt-2)] leading-relaxed">
                {nota.observacao}
              </p>
            </div>
          ) : null}

          {nota.cartasCorrecao && nota.cartasCorrecao.length > 0 ? (
            <div className="flex flex-col gap-2">
              <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
                Cartas de correção
              </span>
              <ul className="flex flex-col gap-2">
                {nota.cartasCorrecao.map((c) => (
                  <li
                    key={c.sequencia}
                    className="rounded-md border p-3 text-sm"
                    style={{
                      background: "var(--color-card-2)",
                      borderColor: "var(--color-line-2)",
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <Pill tom="info">CC-e #{c.sequencia}</Pill>
                      <span className="text-[11px] text-[var(--color-txt-3)] mono">
                        {formatarDataHoraBR(c.emitidaEm)}
                      </span>
                    </div>
                    <p className="text-[var(--color-txt)] mt-2 leading-relaxed">
                      {c.texto}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {nota.status === "cancelada" && nota.canceladaEm ? (
            <div
              className="rounded-md border p-3 flex flex-col gap-1"
              style={{
                background: "var(--color-red-d)",
                borderColor: "rgba(255,85,102,0.32)",
              }}
            >
              <span className="text-[10px] uppercase tracking-[0.14em] font-bold mono text-[var(--color-red)]">
                Nota cancelada
              </span>
              <span className="text-[12px] text-[var(--color-txt-2)]">
                {formatarDataHoraBR(nota.canceladaEm)} ·{" "}
                {nota.motivoCancelamento ?? "sem motivo registrado"}
              </span>
            </div>
          ) : null}
        </Card>

        <Card className="p-5 flex flex-col gap-3 self-start">
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Totais
          </span>
          <Linha label="Produtos / serviços" valor={nota.totais.produtos} />
          {nota.totais.icms > 0 ? <Linha label="ICMS" valor={nota.totais.icms} sub /> : null}
          {nota.totais.iss > 0 ? <Linha label="ISS" valor={nota.totais.iss} sub /> : null}
          {nota.totais.pis > 0 ? <Linha label="PIS" valor={nota.totais.pis} sub /> : null}
          {nota.totais.cofins > 0 ? <Linha label="Cofins" valor={nota.totais.cofins} sub /> : null}
          <div
            className="border-t pt-3 flex items-baseline justify-between"
            style={{ borderColor: "var(--color-line)" }}
          >
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Total da nota
            </span>
            <span className="mono text-2xl font-extrabold text-[var(--color-txt)]">
              <Moeda valor={nota.totais.valorNota} />
            </span>
          </div>

          <div
            className="rounded-md border p-3 flex items-start gap-2 mt-1"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            <CalendarClock className="size-4 text-[var(--color-blue)] mt-0.5" />
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
                Emissão
              </span>
              <span className="text-sm text-[var(--color-txt)]">
                {formatarDataHoraBR(nota.emitidaEm)}
              </span>
              {nota.pagamento ? (
                <span className="text-[11px] text-[var(--color-txt-3)] mt-1">
                  Pagamento via {nota.pagamento.forma.replace("_", " ")} · vence{" "}
                  {nota.pagamento.vencimento
                    ? formatarDataBR(nota.pagamento.vencimento)
                    : "—"}
                </span>
              ) : null}
            </div>
          </div>
        </Card>
      </div>

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
            className="rounded-md border bg-[var(--color-card-2)] border-[var(--color-line-2)] px-3 py-2 text-sm text-[var(--color-txt)] placeholder:text-[var(--color-txt-3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-lime)]/30"
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

      <Dialog open={cceAberto} onOpenChange={setCceAberto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Carta de correção eletrônica</DialogTitle>
            <DialogDescription>
              Use pra corrigir informações da nota que não impactam valores ou
              destinatário.
            </DialogDescription>
          </DialogHeader>
          <textarea
            value={textoCce}
            onChange={(e) => setTextoCce(e.target.value)}
            placeholder="Descreva a correção..."
            rows={4}
            className="rounded-md border bg-[var(--color-card-2)] border-[var(--color-line-2)] px-3 py-2 text-sm text-[var(--color-txt)] placeholder:text-[var(--color-txt-3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-lime)]/30"
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
    </div>
  );
}

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
      className="rounded-md border p-4 flex flex-col gap-2"
      style={{
        background: "var(--color-card-2)",
        borderColor: "var(--color-line-2)",
      }}
    >
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 text-[var(--color-txt-3)]" />
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
          {titulo}
        </span>
      </div>
      <span className="text-base font-semibold text-[var(--color-txt)] leading-tight">
        {nome}
      </span>
      <span className="mono text-xs text-[var(--color-txt-2)]">
        {documento}
      </span>
      {endereco ? (
        <span className="text-[11px] text-[var(--color-txt-3)] leading-snug">
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
            ? "text-[11px] text-[var(--color-txt-3)]"
            : "text-sm text-[var(--color-txt-2)]"
        }
      >
        {label}
      </span>
      <span
        className={
          sub
            ? "mono text-[11px] text-[var(--color-txt-3)]"
            : "mono text-sm text-[var(--color-txt)]"
        }
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}
