"use client";

import * as React from "react";
import Link from "next/link";
import { Plus, RefreshCw, Wallet } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { BancoLogo } from "@/components/controles/banco-logo";
import {
  useBancos,
  useSincronizarBanco,
} from "@/hooks/use-controles";
import type { ContaBancaria } from "@/lib/schemas/controles";

export default function BancosPage() {
  const { data, isLoading, isError, refetch } = useBancos();

  const saldoTotal = React.useMemo(
    () => (data ?? []).reduce((acc, c) => acc + c.saldo, 0),
    [data]
  );

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Controles · Bancos
          </span>
          <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Suas contas bancárias
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
            Saldos sincronizados via Open Finance. Tudo o que entra e sai
            aparece aqui automaticamente.
          </p>
        </div>
        <Button asChild>
          <Link href="/controles/bancos/conectar">
            <Plus className="size-4" /> Conectar nova conta
          </Link>
        </Button>
      </header>

      <ControlesSubnav />

      {isLoading ? (
        <LoadingState titulo="Carregando contas..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma conta conectada"
          descricao="Conecte seu primeiro banco via Open Finance e o FiscalAI traz saldo e transações automaticamente."
          icone={Wallet}
          acao={
            <Button asChild>
              <Link href="/controles/bancos/conectar">
                <Plus className="size-4" /> Conectar conta
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard
              label="Saldo total"
              valor={<Moeda valor={saldoTotal} />}
              pill={{ tom: "ok", texto: "atualizado" }}
              sub={`${data.length} ${data.length === 1 ? "conta conectada" : "contas conectadas"}`}
            />
            <StatCard
              label="Maior saldo"
              valor={
                <Moeda
                  valor={Math.max(...data.map((c) => c.saldo))}
                />
              }
              sub={
                data.find(
                  (c) => c.saldo === Math.max(...data.map((d) => d.saldo))
                )?.bancoNome
              }
            />
            <StatCard
              label="Última sincronização"
              valor={
                ultimoSyncMaisRecente(data) ? (
                  <span className="text-base">
                    {formatarSync(ultimoSyncMaisRecente(data)!)}
                  </span>
                ) : (
                  "—"
                )
              }
              sub="Atualiza a cada 4 horas"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.map((conta) => (
              <ContaCard key={conta.id} conta={conta} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ContaCard({ conta }: { conta: ContaBancaria }) {
  const sincronizar = useSincronizarBanco();
  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <BancoLogo
            cor={conta.cor}
            textoCor={conta.textoCor}
            iniciais={conta.iniciais}
            size="lg"
          />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--color-txt)] truncate">
              {conta.apelido}
            </p>
            <p className="mono text-[11px] text-[var(--color-txt-3)]">
              Ag {conta.agencia} · CC {conta.numero}
            </p>
          </div>
        </div>
        <Pill tom="ok">conectado</Pill>
      </div>

      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.14em] font-semibold text-[var(--color-txt-3)]">
            Saldo
          </p>
          <p className="mono text-2xl font-bold text-[var(--color-txt)]">
            <Moeda valor={conta.saldo} />
          </p>
        </div>
        <p className="text-[11px] text-[var(--color-txt-3)] text-right">
          Última sync<br />
          <span className="mono text-[var(--color-txt-2)]">
            {formatarSync(conta.ultimoSyncEm)}
          </span>
        </p>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button asChild variant="outline" className="flex-1">
          <Link href={`/controles/bancos/${conta.id}`}>Ver extrato</Link>
        </Button>
        <Button
          variant="ghost"
          disabled={sincronizar.isPending}
          onClick={async () => {
            await sincronizar.mutateAsync(conta.id);
            toast.success(`${conta.bancoNome} sincronizado`);
          }}
          aria-label={`Sincronizar ${conta.bancoNome}`}
        >
          <RefreshCw
            className={`size-4 ${
              sincronizar.isPending && sincronizar.variables === conta.id
                ? "animate-spin"
                : ""
            }`}
          />
          Sincronizar
        </Button>
      </div>
    </Card>
  );
}

function ultimoSyncMaisRecente(contas: ContaBancaria[]): string | null {
  if (contas.length === 0) return null;
  return contas
    .map((c) => c.ultimoSyncEm)
    .sort((a, b) => b.localeCompare(a))[0] ?? null;
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
