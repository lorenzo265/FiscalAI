"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Banknote,
  Building2,
  Landmark,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Pill, type PillTom } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { formatarDataHoraBR } from "@/lib/format/data";
import { toast } from "sonner";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

const STORAGE_KEY = "analista-fiscal:integracoes-toggles";

type IntegracaoId = "open-finance" | "ecac" | "esocial" | "rfb";

interface IntegracaoConfig {
  id: IntegracaoId;
  titulo: string;
  descricao: string;
  icone: LucideIcon;
  conectadaPadrao: boolean;
}

const INTEGRACOES: IntegracaoConfig[] = [
  {
    id: "open-finance",
    titulo: "Open Finance",
    descricao:
      "Sincroniza saldos e extratos dos bancos conectados, automatizando a conciliação.",
    icone: Banknote,
    conectadaPadrao: true,
  },
  {
    id: "ecac",
    titulo: "Portal e-CAC",
    descricao:
      "Acessa intimações, certidões e parcelamentos diretamente na Receita Federal.",
    icone: Landmark,
    conectadaPadrao: false,
  },
  {
    id: "esocial",
    titulo: "eSocial",
    descricao:
      "Transmite eventos da folha (S-2200, S-1200, S-2299) sem sair do painel.",
    icone: UsersRound,
    conectadaPadrao: true,
  },
  {
    id: "rfb",
    titulo: "Receita Federal — CNPJ",
    descricao:
      "Verifica situação cadastral, sócios e atividades automaticamente a cada 7 dias.",
    icone: Building2,
    conectadaPadrao: true,
  },
];

function lerToggles(): Record<IntegracaoId, boolean> {
  if (typeof window === "undefined") {
    return INTEGRACOES.reduce(
      (acc, i) => ({ ...acc, [i.id]: i.conectadaPadrao }),
      {} as Record<IntegracaoId, boolean>
    );
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaults(), ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return defaults();
}

function defaults(): Record<IntegracaoId, boolean> {
  return INTEGRACOES.reduce(
    (acc, i) => ({ ...acc, [i.id]: i.conectadaPadrao }),
    {} as Record<IntegracaoId, boolean>
  );
}

export default function ConfiguracoesIntegracoesPage() {
  const { empresa } = useEmpresaAtual();
  const [toggles, setToggles] = React.useState<Record<IntegracaoId, boolean>>(
    defaults
  );
  const reduced = useReducedMotion();

  React.useEffect(() => {
    setToggles(lerToggles());
  }, []);

  function alternar(id: IntegracaoId, ligada: boolean) {
    const novos = { ...toggles, [id]: ligada };
    setToggles(novos);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(novos));
    } catch {
      /* ignore */
    }
    const titulo = INTEGRACOES.find((i) => i.id === id)?.titulo ?? "Integração";
    toast.success(
      ligada ? `${titulo} reconectada` : `${titulo} desativada`,
      {
        description: ligada
          ? "Sincronização retomada — pode levar alguns minutos."
          : "A sincronização vai parar até você reativar.",
      }
    );
  }

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
        <motion.div variants={itemVariants}>
          <Link
            href="/configuracoes"
            className="text-[11px] mono uppercase tracking-[0.12em] text-[var(--color-ink-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-ink-2)] transition-colors"
          >
            <ArrowLeft className="size-3" />
            Configurações
          </Link>
        </motion.div>
        <motion.h1
          variants={itemVariants}
          className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight mt-1"
        >
          Integrações
        </motion.h1>
        <motion.p
          variants={itemVariants}
          className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
        >
          Conexões que automatizam o trabalho operacional. Mantenha tudo ativo
          para reduzir lançamentos manuais.
        </motion.p>
      </motion.header>

      <ConfiguracoesSubnav />

      {/* Fig. 01 — lista de integrações */}
      <Framed marks={false} tone="rule" surface="card" padded={false}>
        <div className="px-5 pt-4 pb-2">
          <Fig n={1} titulo="Conexões disponíveis" size="sm" />
        </div>
        <Ruler />
        <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
          {INTEGRACOES.map((integ) => (
            <LinhaIntegracao
              key={integ.id}
              integ={integ}
              ligada={toggles[integ.id]}
              onChange={(v) => alternar(integ.id, v)}
              bancosConectados={
                integ.id === "open-finance"
                  ? empresa?.bancosConectados?.length ?? 0
                  : null
              }
              ultimaSync={
                integ.id === "open-finance"
                  ? empresa?.bancosConectados?.[0]?.ultimaSync ?? null
                  : null
              }
            />
          ))}
        </ul>
      </Framed>
    </motion.div>
  );
}

function LinhaIntegracao({
  integ,
  ligada,
  onChange,
  bancosConectados,
  ultimaSync,
}: {
  integ: IntegracaoConfig;
  ligada: boolean;
  onChange: (v: boolean) => void;
  bancosConectados: number | null;
  ultimaSync: string | null;
}) {
  const Icon = integ.icone;
  const tom: PillTom = ligada ? "ok" : "neutral";

  return (
    <li className="px-5 py-4 flex flex-col md:flex-row md:items-center gap-4 hover:bg-[var(--color-paper-2)] transition-colors">
      {/* ícone em quadrado técnico */}
      <div
        className="size-10 rounded-[var(--radius-sm)] grid place-items-center shrink-0 border"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule)",
        }}
      >
        <Icon
          className="size-5"
          style={{
            color: ligada ? "var(--color-green)" : "var(--color-ink-3)",
          }}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold text-[var(--color-ink)]">
            {integ.titulo}
          </span>
          <Pill tom={tom}>{ligada ? "conectada" : "desativada"}</Pill>
        </div>
        <p className="text-xs text-[var(--color-ink-2)] mt-1 leading-relaxed">
          {integ.descricao}
        </p>
        {bancosConectados != null && ligada ? (
          <p className="text-[11px] text-[var(--color-ink-3)] mt-1.5 mono">
            {bancosConectados} banco{bancosConectados === 1 ? "" : "s"}{" "}
            conectado{bancosConectados === 1 ? "" : "s"}
            {ultimaSync
              ? ` · última sincronização ${formatarDataHoraBR(ultimaSync)}`
              : ""}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <span className="text-[11px] text-[var(--color-ink-3)] mono uppercase tracking-[0.12em] font-bold hidden md:inline">
          {ligada ? "ligada" : "desligada"}
        </span>
        <Switch
          checked={ligada}
          onCheckedChange={onChange}
          aria-label={`Alternar ${integ.titulo}`}
        />
      </div>
    </li>
  );
}
