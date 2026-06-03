"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Building2,
  Plug2,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { ResetDemoButton } from "@/components/configuracoes/reset-demo-button";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { emailLogado } from "@/lib/auth";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

interface CardConfig {
  href: string;
  rotulo: string;
  titulo: string;
  descricao: string;
  icone: LucideIcon;
  pill: { tom: PillTom; texto: string };
}

export default function ConfiguracoesPage() {
  const { empresa } = useEmpresaAtual();
  const [email, setEmail] = React.useState<string | null>(null);
  const reduced = useReducedMotion();

  React.useEffect(() => {
    setEmail(emailLogado());
  }, []);

  const certificadoOk = !!empresa?.certificadoA1;
  const bancosCount = empresa?.bancosConectados?.length ?? 0;

  const cards: CardConfig[] = [
    {
      href: "/configuracoes/empresa",
      rotulo: "Cadastro",
      titulo: "Empresa",
      descricao: empresa
        ? `${empresa.razaoSocial} · ${empresa.uf}`
        : "Razão social, regime e endereço.",
      icone: Building2,
      pill: { tom: "ok", texto: "ativo" },
    },
    {
      href: "/configuracoes/certificado",
      rotulo: "NF-e",
      titulo: "Certificado digital",
      descricao: certificadoOk
        ? `Arquivo ${empresa!.certificadoA1!.nomeArquivo} carregado.`
        : "Sem certificado A1 — emissão de NF-e indisponível.",
      icone: ShieldCheck,
      pill: certificadoOk
        ? { tom: "ok", texto: "instalado" }
        : { tom: "warn", texto: "pendente" },
    },
    {
      href: "/configuracoes/integracoes",
      rotulo: "Conexões",
      titulo: "Integrações",
      descricao:
        bancosCount > 0
          ? `Open Finance com ${bancosCount} banco${bancosCount === 1 ? "" : "s"} conectado${bancosCount === 1 ? "" : "s"}.`
          : "Conecte bancos, e-CAC, eSocial e Receita Federal.",
      icone: Plug2,
      pill:
        bancosCount > 0
          ? { tom: "ok", texto: `${bancosCount} ativos` }
          : { tom: "neutral", texto: "configurar" },
    },
    {
      href: "/configuracoes/usuarios",
      rotulo: "Equipe",
      titulo: "Usuários",
      descricao: email
        ? `${email} (administrador). Convide seu contador ou sócio.`
        : "Convide seu contador ou sócio.",
      icone: Users,
      pill: { tom: "neutral", texto: "1 usuário" },
    },
  ];

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
      <motion.header variants={containerVariants} initial="hidden" animate="show">
        <motion.span
          variants={itemVariants}
          className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
        >
          Conta · Configurações
        </motion.span>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
        >
          Ajustes da conta
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          Dados cadastrais, certificado digital, integrações com bancos e
          governo, e controle de acesso.
        </motion.p>
      </motion.header>

      <ConfiguracoesSubnav />

      {/* grade de módulos de configuração */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cards.map((c) => (
          <CardConfiguracao key={c.href} {...c} />
        ))}
      </div>

      {/* rodapé de demo */}
      <div
        className="flex items-center justify-between border-t pt-4 mt-2"
        style={{ borderColor: "var(--color-rule)" }}
      >
        <p className="text-[11px] text-[var(--color-ink-3)] mono">
          Demonstração local — nenhum dado é enviado a servidores externos.
        </p>
        <ResetDemoButton />
      </div>
    </motion.div>
  );
}

function CardConfiguracao({
  href,
  rotulo,
  titulo,
  descricao,
  icone: Icon,
  pill,
}: CardConfig) {
  return (
    <Link href={href} className="block group">
      <Framed
        marks={false}
        tone="rule"
        surface="card"
        className="flex items-start gap-4 h-full transition-colors group-hover:border-[var(--color-rule-2)]"
      >
        {/* ícone em quadrado técnico */}
        <div
          className="size-10 rounded-[var(--radius-sm)] grid place-items-center shrink-0 border"
          style={{
            background: "var(--color-paper-2)",
            borderColor: "var(--color-rule)",
          }}
        >
          <Icon className="size-5" style={{ color: "var(--color-green)" }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] mono uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)]">
              {rotulo}
            </span>
            <Pill tom={pill.tom}>{pill.texto}</Pill>
          </div>
          <p className="text-sm font-bold text-[var(--color-ink)] mt-0.5">
            {titulo}
          </p>
          <p className="text-xs text-[var(--color-ink-2)] mt-1 leading-relaxed line-clamp-2">
            {descricao}
          </p>
        </div>
        <ArrowRight
          className="size-4 text-[var(--color-ink-3)] group-hover:text-[var(--color-ink)] transition-colors mt-1 shrink-0"
        />
      </Framed>
    </Link>
  );
}
