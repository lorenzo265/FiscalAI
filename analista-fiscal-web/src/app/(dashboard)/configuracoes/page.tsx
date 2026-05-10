"use client";

import Link from "next/link";
import {
  ArrowRight,
  Building2,
  Plug2,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill, type PillTom } from "@/components/shared/pill";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { ResetDemoButton } from "@/components/configuracoes/reset-demo-button";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { emailLogado } from "@/lib/auth";
import * as React from "react";

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

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Conta · Configurações
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Ajustes da sua conta
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Tudo o que define sua empresa por aqui: dados cadastrais, certificado
          digital, integrações com bancos e governo, e quem mais tem acesso.
        </p>
      </header>

      <ConfiguracoesSubnav />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cards.map((c) => (
          <CardConfiguracao key={c.href} {...c} />
        ))}
      </div>

      <div className="flex items-center justify-between border-t pt-4 mt-2"
        style={{ borderColor: "var(--color-line)" }}
      >
        <p className="text-[11px] text-[var(--color-txt-3)]">
          Esta é uma demonstração local. Nada é enviado para servidores externos.
        </p>
        <ResetDemoButton />
      </div>
    </div>
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
      <Card interactive className="p-5 flex items-start gap-4 h-full">
        <div
          className="size-10 rounded-md grid place-items-center shrink-0"
          style={{ background: "var(--color-card-2)" }}
        >
          <Icon className="size-5 text-[var(--color-lime)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)]">
              {rotulo}
            </span>
            <Pill tom={pill.tom}>{pill.texto}</Pill>
          </div>
          <p className="text-base font-bold text-[var(--color-txt)] mt-0.5">
            {titulo}
          </p>
          <p className="text-xs text-[var(--color-txt-2)] mt-1 leading-relaxed line-clamp-2">
            {descricao}
          </p>
        </div>
        <ArrowRight className="size-4 text-[var(--color-txt-3)] group-hover:text-[var(--color-txt)] transition-colors mt-1" />
      </Card>
    </Link>
  );
}
