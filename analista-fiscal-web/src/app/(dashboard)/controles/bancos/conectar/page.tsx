"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Framed } from "@/components/blueprint/framed";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { BancoLogo } from "@/components/controles/banco-logo";
import { BancoConectarModal } from "@/components/onboarding/banco-conectar-modal";
import { useBancos, useConectarBanco } from "@/hooks/use-controles";
import {
  BANCOS_OPENFINANCE,
  type BancoOpenFinance,
} from "@/lib/mocks/seeds/bancos-openfinance";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import { cn } from "@/lib/utils";

export default function ConectarBancoPage() {
  const router = useRouter();
  const { data: contasConectadas } = useBancos();
  const conectar = useConectarBanco();
  const reduced = useReducedMotion();

  const [bancoSelecionado, setBancoSelecionado] =
    React.useState<BancoOpenFinance | null>(null);

  async function aoSucesso() {
    if (!bancoSelecionado) return;
    try {
      const conta = await conectar.mutateAsync(bancoSelecionado.id);
      toast.success(`${conta.bancoNome} conectado`, {
        description: "30 dias de transações importados.",
      });
      setBancoSelecionado(null);
      router.push("/controles/bancos");
    } catch {
      toast.error("Não foi possível concluir a conexão.");
    }
  }

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
      {/* ── cabeçalho ── */}
      <motion.header
        className="flex flex-col gap-2"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={itemV}>
          <Button asChild variant="ghost" className="self-start -ml-2">
            <Link href="/controles/bancos">
              <ArrowLeft className="size-4" /> Voltar para bancos
            </Link>
          </Button>
        </motion.div>
        <motion.span
          variants={itemV}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold"
        >
          Controles · Conectar conta
        </motion.span>
        <motion.h1
          variants={itemV}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Conectar uma conta bancária
        </motion.h1>
        <motion.p
          variants={itemV}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl"
        >
          Selecione seu banco abaixo. Você será redirecionado para autorizar o
          Arkan via Open Finance — acesso somente leitura, regulado pelo
          Banco Central.
        </motion.p>
      </motion.header>

      <ControlesSubnav />

      {/* ── aviso de segurança ── */}
      <Framed
        marks={false}
        tone="rule"
        surface="paper-2"
        className="flex items-center gap-3"
        style={{ borderColor: "var(--color-green)" }}
      >
        <ShieldCheck
          className="size-5 shrink-0"
          style={{ color: "var(--color-green)" }}
        />
        <p className="text-sm text-[var(--color-ink)]">
          Open Finance é o protocolo do Banco Central que permite conectar
          contas com segurança. O Arkan <strong>nunca</strong> movimenta seu
          dinheiro — só lê o extrato.
        </p>
      </Framed>

      {/* ── grid de bancos ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {BANCOS_OPENFINANCE.map((banco) => {
          const jaConectado = contasConectadas?.some(
            (c) => c.bancoId === banco.id
          );
          return (
            <button
              key={banco.id}
              type="button"
              disabled={jaConectado}
              onClick={() => setBancoSelecionado(banco)}
              className={cn(
                "rounded-[var(--radius-md)] border p-4 transition-all text-left flex flex-col gap-3",
                jaConectado
                  ? "border-[var(--color-green)] bg-[var(--color-paper-2)] cursor-default"
                  : "border-[var(--color-rule)] bg-[var(--color-paper-2)] hover:bg-[var(--color-paper)] hover:border-[var(--color-ink-2)]"
              )}
            >
              <div className="flex items-center justify-between">
                <BancoLogo
                  cor={banco.cor}
                  textoCor={banco.textoCor}
                  iniciais={banco.iniciais}
                  size="md"
                />
                {jaConectado ? (
                  <span className="mono text-[9px] uppercase tracking-[0.16em] font-bold text-[var(--color-green)]">
                    conectado
                  </span>
                ) : null}
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  {banco.nome}
                </p>
                <p className="text-[11px] text-[var(--color-ink-3)] mt-0.5">
                  {jaConectado ? "Conta já vinculada" : "Open Finance · BCB"}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      <BancoConectarModal
        banco={bancoSelecionado}
        open={!!bancoSelecionado}
        onOpenChange={(v) => {
          if (!v) setBancoSelecionado(null);
        }}
        onSucesso={() => {
          void aoSucesso();
        }}
      />
    </motion.div>
  );
}
