"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Mail, Send, X } from "lucide-react";
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
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { ComplianceSubnav } from "@/components/compliance/compliance-subnav";
import {
  useEnviarIntimacaoAoContador,
  useIntimacoes,
  useMarcarIntimacaoLida,
} from "@/hooks/use-compliance";
import {
  ORGAO_LABEL,
  type Intimacao,
  type StatusIntimacao,
} from "@/lib/schemas/compliance";
import { formatarDataBR, formatarDataHoraBR } from "@/lib/format/data";

const STATUS_TOM: Record<StatusIntimacao, "warn" | "info" | "ok" | "neutral"> = {
  nova: "warn",
  lida: "info",
  em_resposta: "info",
  respondida: "ok",
  encerrada: "neutral",
};

const STATUS_LABEL: Record<StatusIntimacao, string> = {
  nova: "nova",
  lida: "lida",
  em_resposta: "em resposta",
  respondida: "respondida",
  encerrada: "encerrada",
};

export default function IntimacoesPage() {
  const { data, isLoading, isError, refetch } = useIntimacoes();
  const [selecionada, setSelecionada] = React.useState<Intimacao | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Compliance · Intimações
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Intimações fiscais
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Mensagens da Receita, PGFN, INSS, Sefaz, Prefeitura e Ministério do
          Trabalho. A gente busca todo dia no e-CAC e nos portais oficiais.
        </p>
      </header>

      <ComplianceSubnav />

      {isLoading ? (
        <LoadingState titulo="Buscando intimações..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma intimação"
          descricao="Sua caixa postal eletrônica está vazia. Você pode dormir tranquilo."
          icone={Mail}
        />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y" style={{ borderColor: "var(--color-line)" }}>
            {data.map((i) => (
              <LinhaIntimacao
                key={i.id}
                intimacao={i}
                onAbrir={() => setSelecionada(i)}
              />
            ))}
          </ul>
        </Card>
      )}

      <DetalheIntimacaoDialog
        intimacao={selecionada}
        onClose={() => setSelecionada(null)}
      />
    </div>
  );
}

function LinhaIntimacao({
  intimacao,
  onAbrir,
}: {
  intimacao: Intimacao;
  onAbrir: () => void;
}) {
  const dias = Math.ceil(
    (new Date(intimacao.prazoResposta).getTime() - Date.now()) /
      (24 * 60 * 60 * 1000)
  );

  return (
    <li
      className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors cursor-pointer"
      onClick={onAbrir}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onAbrir();
        }
      }}
    >
      <div className="flex flex-col shrink-0 w-32">
        <span className="mono text-xs font-bold text-[var(--color-txt)]">
          {ORGAO_LABEL[intimacao.orgao]}
        </span>
        <Pill tom={STATUS_TOM[intimacao.status]}>
          {STATUS_LABEL[intimacao.status]}
        </Pill>
      </div>
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm font-semibold text-[var(--color-txt)] truncate">
          {intimacao.assunto}
        </span>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-txt-3)] mono flex-wrap">
          <span>Protocolo {intimacao.protocolo}</span>
          <span className="size-1 rounded-full bg-[var(--color-line-2)]" />
          <span>Recebida {formatarDataHoraBR(intimacao.recebidoEm)}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Pill
          tom={
            dias < 0
              ? "error"
              : dias <= 7
                ? "warn"
                : "neutral"
          }
        >
          {dias < 0
            ? `prazo vencido há ${Math.abs(dias)}d`
            : `prazo em ${dias}d`}
        </Pill>
        {intimacao.enviadoContador ? (
          <Pill tom="info">
            <span className="flex items-center gap-1">
              <CheckCircle2 className="size-3" /> contador
            </span>
          </Pill>
        ) : null}
      </div>
    </li>
  );
}

function DetalheIntimacaoDialog({
  intimacao,
  onClose,
}: {
  intimacao: Intimacao | null;
  onClose: () => void;
}) {
  const marcarLida = useMarcarIntimacaoLida();
  const enviar = useEnviarIntimacaoAoContador();

  if (!intimacao) return null;

  return (
    <Dialog
      open={!!intimacao}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
    >
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center justify-between gap-3">
            <DialogTitle>{intimacao.assunto}</DialogTitle>
            <button
              type="button"
              onClick={onClose}
              className="text-[var(--color-txt-3)] hover:text-[var(--color-txt)]"
              aria-label="Fechar"
            >
              <X className="size-4" />
            </button>
          </div>
          <DialogDescription>
            {ORGAO_LABEL[intimacao.orgao]} · Protocolo {intimacao.protocolo} ·
            Recebida {formatarDataHoraBR(intimacao.recebidoEm)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 flex-wrap">
          <Pill tom={STATUS_TOM[intimacao.status]}>
            {STATUS_LABEL[intimacao.status]}
          </Pill>
          <Pill tom="warn">
            Prazo até {formatarDataBR(intimacao.prazoResposta)}
          </Pill>
          {intimacao.enviadoContador ? (
            <Pill tom="info">enviada ao contador</Pill>
          ) : null}
        </div>

        <div
          className="rounded-md border p-4 max-h-[320px] overflow-y-auto whitespace-pre-line text-sm leading-relaxed"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
            color: "var(--color-txt)",
          }}
        >
          {intimacao.texto}
        </div>

        <DialogFooter>
          {intimacao.status === "nova" ? (
            <Button
              variant="outline"
              disabled={marcarLida.isPending}
              onClick={async () => {
                await marcarLida.mutateAsync(intimacao.id);
                toast.success("Intimação marcada como lida");
              }}
            >
              {marcarLida.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <CheckCircle2 className="size-4" />
              )}
              Marcar como lida
            </Button>
          ) : null}
          <Button
            disabled={enviar.isPending || intimacao.enviadoContador}
            onClick={async () => {
              await enviar.mutateAsync(intimacao.id);
              toast.success("Encaminhada ao contador", {
                description: "O contador recebeu uma notificação por e-mail.",
              });
            }}
          >
            {enviar.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            {intimacao.enviadoContador
              ? "Já enviada ao contador"
              : "Enviar pra meu contador"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
