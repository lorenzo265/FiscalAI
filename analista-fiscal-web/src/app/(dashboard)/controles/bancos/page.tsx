"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, RefreshCw, Wallet } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { Framed } from "@/components/blueprint/framed";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { BancoLogo } from "@/components/controles/banco-logo";
import {
  useBancos,
  useSincronizarBanco,
} from "@/hooks/use-controles";
import { useCountUp } from "@/lib/motion/use-count-up";
import { formatarMoeda } from "@/lib/format/moeda";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import type { ContaBancaria } from "@/lib/schemas/controles";

export default function BancosPage() {
  const { data, isLoading, isError, refetch } = useBancos();
  const reduced = useReducedMotion();

  const saldoTotal = React.useMemo(
    () => (data ?? []).reduce((acc, c) => acc + c.saldo, 0),
    [data]
  );

  /* ── número-herói: saldo total consolidado ── */
  const saldoCentavos = Math.round(saldoTotal * 100);
  const heroRaw = useCountUp(saldoCentavos, {
    id: "bancos:saldoTotal",
    format: Math.round,
  });
  const heroFormatado = formatarMoeda(heroRaw / 100);

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
      {/* ── Bloco 1: cabeçalho + número-herói + ação primária ── */}
      <motion.header
        className="flex flex-col gap-4"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <motion.span
              variants={itemV}
              className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
            >
              Controles · Bancos
            </motion.span>
            <motion.h1
              variants={itemV}
              className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
            >
              Contas bancárias
            </motion.h1>
          </div>

          {/* Ação primária — verde 44px */}
          <motion.div variants={itemV} className="shrink-0 pt-5 md:pt-6">
            <Button asChild size="default" className="h-11 px-5 gap-2">
              <Link href="/controles/bancos/conectar">
                <Plus className="size-4" aria-hidden />
                Conectar conta
              </Link>
            </Button>
          </motion.div>
        </div>

        {/* número-herói: saldo total */}
        {data && data.length > 0 ? (
          <motion.div variants={itemV} className="flex flex-col gap-1">
            <span
              className="mono leading-none text-[var(--color-ink)] whitespace-nowrap"
              style={{
                fontSize: "clamp(2.5rem, 8vw, 4.5rem)",
                fontWeight: 300,
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.02em",
              }}
              aria-label={`Saldo total: ${heroFormatado}`}
            >
              {heroFormatado}
            </span>
            <span className="text-[13px] text-[var(--color-ink-2)] font-medium">
              saldo consolidado em{" "}
              <span className="text-[var(--color-ink)]">
                {data.length} {data.length === 1 ? "conta conectada" : "contas conectadas"}
              </span>
            </span>
          </motion.div>
        ) : null}
      </motion.header>

      <ControlesSubnav />

      {isLoading ? (
        <LoadingState titulo="Carregando contas..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          titulo="Nenhuma conta conectada"
          descricao="Conecte seu primeiro banco via Open Finance e o Arkan traz saldo e transações automaticamente."
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
                <Moeda valor={Math.max(...data.map((c) => c.saldo))} />
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
                  <span className="text-base mono">
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
    </motion.div>
  );
}

function ContaCard({ conta }: { conta: ContaBancaria }) {
  const sincronizar = useSincronizarBanco();
  return (
    <Framed marks={false} tone="rule" surface="card" padded={false} className="flex flex-col">
      <div className="px-4 pt-4 pb-3 flex items-start justify-between gap-3 border-b border-[var(--color-rule)]">
        <div className="flex items-center gap-3 min-w-0">
          <BancoLogo
            cor={conta.cor}
            textoCor={conta.textoCor}
            iniciais={conta.iniciais}
            size="lg"
          />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--color-ink)] truncate">
              {conta.apelido}
            </p>
            <p
              className="mono text-[11px] text-[var(--color-ink-2)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              <abbr title="Agência">Ag</abbr> {conta.agencia} ·{" "}
              <abbr title="Conta Corrente">CC</abbr> {conta.numero}
            </p>
          </div>
        </div>
        <Pill tom="ok">conectado</Pill>
      </div>

      <div className="px-4 py-3 flex items-end justify-between gap-3 border-b border-[var(--color-rule)]">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--color-ink-2)] block mb-1">
            Saldo
          </span>
          <p
            className="mono text-2xl font-bold text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            <Moeda valor={conta.saldo} />
          </p>
        </div>
        <p className="text-[11px] text-[var(--color-ink-2)] text-right">
          Última sync<br />
          <span
            className="mono text-[var(--color-ink-2)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formatarSync(conta.ultimoSyncEm)}
          </span>
        </p>
      </div>

      <div className="px-4 py-3 flex items-center gap-2">
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
    </Framed>
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
