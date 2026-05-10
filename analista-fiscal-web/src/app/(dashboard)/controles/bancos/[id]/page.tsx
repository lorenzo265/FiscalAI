"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowDownLeft,
  ArrowLeft,
  ArrowUpRight,
  Check,
  Link2,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { useQueryStates, parseAsString } from "nuqs";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { Pill } from "@/components/shared/pill";
import { StatCard } from "@/components/shared/stat-card";
import { Moeda } from "@/components/shared/moeda";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { BancoLogo } from "@/components/controles/banco-logo";
import { ModalConciliar } from "@/components/controles/modal-conciliar";
import {
  useBanco,
  useSincronizarBanco,
  useTransacoes,
  useConciliarTransacao,
} from "@/hooks/use-controles";
import {
  CATEGORIA_LABEL,
  type TransacaoBancaria,
} from "@/lib/schemas/controles";
import { formatarDataBR } from "@/lib/format/data";
import { cn } from "@/lib/utils";

export default function ExtratoBancoPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const {
    data: conta,
    isLoading: contaLoading,
    isError: contaErr,
    refetch: refetchConta,
  } = useBanco(id);
  const {
    data: transacoes,
    isLoading: txLoading,
    isError: txErr,
    refetch: refetchTx,
  } = useTransacoes(id);
  const sincronizar = useSincronizarBanco();
  const conciliar = useConciliarTransacao();

  const [filtros, setFiltros] = useQueryStates(
    {
      tipo: parseAsString.withDefault("todos"),
      conciliacao: parseAsString.withDefault("todos"),
      periodo: parseAsString.withDefault("60d"),
    },
    { history: "replace" }
  );

  const [conciliando, setConciliando] = React.useState<TransacaoBancaria | null>(
    null
  );

  const filtradas = React.useMemo<TransacaoBancaria[]>(() => {
    if (!transacoes) return [];
    const corte = corteData(filtros.periodo);
    return transacoes.filter((t) => {
      if (corte && new Date(t.data).getTime() < corte) return false;
      if (filtros.tipo === "credito" && t.tipo !== "credito") return false;
      if (filtros.tipo === "debito" && t.tipo !== "debito") return false;
      if (filtros.conciliacao === "conciliadas" && !t.conciliada) return false;
      if (filtros.conciliacao === "pendentes" && t.conciliada) return false;
      return true;
    });
  }, [transacoes, filtros]);

  const totalConciliadas = (transacoes ?? []).filter((t) => t.conciliada).length;
  const totalPendentes = (transacoes ?? []).length - totalConciliadas;

  if (contaLoading) return <LoadingState titulo="Carregando conta..." />;
  if (contaErr || !conta) {
    return (
      <ErrorState
        titulo="Conta não encontrada"
        descricao="A conta solicitada não existe ou foi removida."
        onTentarNovamente={() => void refetchConta()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <Button asChild variant="ghost" className="self-start -ml-2">
          <Link href="/controles/bancos">
            <ArrowLeft className="size-4" /> Voltar para bancos
          </Link>
        </Button>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <BancoLogo
              cor={conta.cor}
              textoCor={conta.textoCor}
              iniciais={conta.iniciais}
              size="lg"
            />
            <div className="min-w-0">
              <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
                Controles · Extrato
              </span>
              <h1 className="text-[24px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
                {conta.apelido}
              </h1>
              <p className="mono text-xs text-[var(--color-txt-3)]">
                Ag {conta.agencia} · CC {conta.numero}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            disabled={sincronizar.isPending}
            onClick={async () => {
              await sincronizar.mutateAsync(conta.id);
              toast.success("Saldo atualizado");
            }}
          >
            <RefreshCw
              className={cn(
                "size-4",
                sincronizar.isPending && "animate-spin"
              )}
            />
            Sincronizar
          </Button>
        </div>
      </header>

      <ControlesSubnav />

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard
          label="Saldo atual"
          valor={<Moeda valor={conta.saldo} />}
          pill={{ tom: "ok", texto: "atualizado" }}
          sub={`Sync ${formatarSync(conta.ultimoSyncEm)}`}
        />
        <StatCard
          label="Conciliadas"
          valor={
            <span className="text-2xl">
              {totalConciliadas}
              <span className="text-base text-[var(--color-txt-3)]">
                {" / "}
                {(transacoes ?? []).length}
              </span>
            </span>
          }
          pill={{ tom: "ok", texto: "vinculadas" }}
        />
        <StatCard
          label="Pendentes"
          valor={<span className="text-2xl">{totalPendentes}</span>}
          pill={{
            tom: totalPendentes > 0 ? "warn" : "neutral",
            texto: totalPendentes > 0 ? "revisar" : "sem pendência",
          }}
          sub="Vincule a um lançamento contábil"
        />
      </div>

      <Card className="p-4 flex flex-col md:flex-row md:items-center gap-3">
        <Select
          value={filtros.tipo}
          onValueChange={(v) => void setFiltros({ tipo: v })}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todas as movimentações</SelectItem>
            <SelectItem value="credito">Apenas entradas</SelectItem>
            <SelectItem value="debito">Apenas saídas</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filtros.conciliacao}
          onValueChange={(v) => void setFiltros({ conciliacao: v })}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todas</SelectItem>
            <SelectItem value="conciliadas">Conciliadas</SelectItem>
            <SelectItem value="pendentes">Pendentes</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filtros.periodo}
          onValueChange={(v) => void setFiltros({ periodo: v })}
        >
          <SelectTrigger className="w-full md:w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30d">30 dias</SelectItem>
            <SelectItem value="60d">60 dias</SelectItem>
            <SelectItem value="90d">90 dias</SelectItem>
            <SelectItem value="todos">Tudo</SelectItem>
          </SelectContent>
        </Select>
      </Card>

      {txLoading ? (
        <LoadingState titulo="Carregando extrato..." />
      ) : txErr ? (
        <ErrorState onTentarNovamente={() => void refetchTx()} />
      ) : filtradas.length === 0 ? (
        <EmptyState
          titulo="Nenhuma transação no filtro"
          descricao="Ajuste o período ou os filtros."
        />
      ) : (
        <Card className="overflow-hidden">
          <ul
            className="divide-y"
            style={{ borderColor: "var(--color-line)" }}
          >
            {filtradas.map((tx) => (
              <LinhaTransacao
                key={tx.id}
                transacao={tx}
                onConciliar={() => setConciliando(tx)}
                onDesconciliar={async () => {
                  await conciliar.mutateAsync({
                    transacaoId: tx.id,
                    lancamentoId: null,
                  });
                  toast.success("Conciliação removida");
                }}
              />
            ))}
          </ul>
        </Card>
      )}

      <ModalConciliar
        transacao={conciliando}
        aberto={!!conciliando}
        onAbertoChange={(v) => {
          if (!v) setConciliando(null);
        }}
      />
    </div>
  );
}

function LinhaTransacao({
  transacao,
  onConciliar,
  onDesconciliar,
}: {
  transacao: TransacaoBancaria;
  onConciliar: () => void;
  onDesconciliar: () => Promise<void> | void;
}) {
  const credito = transacao.tipo === "credito";
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-card-2)] transition-colors">
      <div className="flex flex-col shrink-0 w-24">
        <span className="mono text-xs font-bold text-[var(--color-txt)]">
          {formatarDataBR(transacao.data)}
        </span>
        <span className="mono text-[10px] text-[var(--color-txt-3)] uppercase tracking-[0.12em]">
          {CATEGORIA_LABEL[transacao.categoria]}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm text-[var(--color-txt)] truncate">
          {transacao.descricao}
        </span>
        {transacao.contraparte ? (
          <span className="text-[11px] text-[var(--color-txt-3)] truncate">
            {transacao.contraparte}
          </span>
        ) : null}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {transacao.conciliada ? (
          <span
            className="flex items-center gap-1 text-[11px] mono text-[var(--color-lime)]"
            title="Conciliada"
          >
            <Check className="size-3.5" /> conciliada
          </span>
        ) : (
          <Pill tom="warn">pendente</Pill>
        )}

        <span
          className={cn(
            "mono text-base font-bold flex items-center gap-1",
            credito ? "text-[var(--color-lime)]" : "text-[var(--color-red)]"
          )}
        >
          {credito ? (
            <ArrowDownLeft className="size-3.5" />
          ) : (
            <ArrowUpRight className="size-3.5" />
          )}
          <Moeda valor={transacao.valor} />
        </span>

        {transacao.conciliada ? (
          <Button
            variant="ghost"
            onClick={() => void onDesconciliar()}
            className="px-2"
            aria-label="Desfazer conciliação"
          >
            Desfazer
          </Button>
        ) : (
          <Button variant="outline" onClick={onConciliar}>
            <Link2 className="size-4" /> Conciliar
          </Button>
        )}
      </div>
    </li>
  );
}

function corteData(periodo: string): number | null {
  const dias =
    periodo === "30d"
      ? 30
      : periodo === "60d"
        ? 60
        : periodo === "90d"
          ? 90
          : null;
  if (dias == null) return null;
  return Date.now() - dias * 24 * 60 * 60 * 1000;
}

function formatarSync(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), {
      addSuffix: true,
      locale: ptBR,
    });
  } catch {
    return "—";
  }
}
