"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Banknote,
  Building2,
  Landmark,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Pill, type PillTom } from "@/components/shared/pill";
import { ConfiguracoesSubnav } from "@/components/configuracoes/configuracoes-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { formatarDataHoraBR } from "@/lib/format/data";
import { toast } from "sonner";

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
      "Sincroniza saldos e extratos dos bancos conectados, automatizando conciliação.",
    icone: Banknote,
    conectadaPadrao: true,
  },
  {
    id: "ecac",
    titulo: "Portal e-CAC",
    descricao:
      "Acessa intimações, certidões e parcelamentos direto da Receita Federal.",
    icone: Landmark,
    conectadaPadrao: false,
  },
  {
    id: "esocial",
    titulo: "eSocial",
    descricao:
      "Transmite eventos da folha (S-2200, S-1200, S-2299) sem sair daqui.",
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

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Link
          href="/configuracoes"
          className="text-[11px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold inline-flex items-center gap-1 hover:text-[var(--color-txt-2)] transition-colors"
        >
          <ArrowLeft className="size-3" />
          Configurações
        </Link>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)] mt-1">
          Integrações
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          Plug-ins que automatizam o que você teria que fazer manualmente.
          Mantenha tudo ligado para reduzir o trabalho operacional.
        </p>
      </header>

      <ConfiguracoesSubnav />

      <div className="flex flex-col gap-3">
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
      </div>
    </div>
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
  const labelStatus = ligada ? "conectada" : "desativada";

  return (
    <Card className="p-5 flex flex-col md:flex-row md:items-center gap-4">
      <div
        className="size-10 rounded-md grid place-items-center shrink-0"
        style={{ background: "var(--color-card-2)" }}
      >
        <Icon
          className="size-5"
          style={{
            color: ligada ? "var(--color-lime)" : "var(--color-txt-3)",
          }}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-base font-bold text-[var(--color-txt)]">
            {integ.titulo}
          </span>
          <Pill tom={tom}>{labelStatus}</Pill>
        </div>
        <p className="text-xs text-[var(--color-txt-2)] mt-1 leading-relaxed">
          {integ.descricao}
        </p>
        {bancosConectados != null && ligada ? (
          <p className="text-[11px] text-[var(--color-txt-3)] mt-1.5 mono">
            {bancosConectados} banco{bancosConectados === 1 ? "" : "s"}{" "}
            conectado{bancosConectados === 1 ? "" : "s"}
            {ultimaSync
              ? ` · última sincronização ${formatarDataHoraBR(ultimaSync)}`
              : ""}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <span className="text-[11px] text-[var(--color-txt-3)] mono uppercase tracking-[0.14em] font-bold hidden md:inline">
          {ligada ? "ligada" : "desligada"}
        </span>
        <Switch
          checked={ligada}
          onCheckedChange={onChange}
          aria-label={`Alternar ${integ.titulo}`}
        />
      </div>
    </Card>
  );
}
