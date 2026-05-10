"use client";

import dynamic from "next/dynamic";
import { FiscalHealthScore } from "@/components/fiscal/fiscal-health-score";
import { ProximoPagamentoCard } from "@/components/home/proximo-pagamento-card";
import { ProximaObrigacaoCard } from "@/components/home/proxima-obrigacao-card";
import { AlertasCard } from "@/components/home/alertas-card";
import { CalendarioMesCard } from "@/components/home/calendario-mes-card";
import { QuickActions } from "@/components/home/quick-actions";
import { SimplesNacionalCard } from "@/components/home/simples-nacional-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

const GraficoReceitaImposto = dynamic(
  () =>
    import("@/components/home/grafico-receita-imposto").then((m) => ({
      default: m.GraficoReceitaImposto,
    })),
  { ssr: false, loading: () => <Skeleton className="h-[280px] w-full" /> }
);

export default function HomePage() {
  const { empresa } = useEmpresaAtual();
  const primeiroNome = empresa?.razaoSocial.split(" ")[0] ?? "";
  const horaSaudacao = saudacao(new Date());

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            {horaSaudacao}
          </span>
          <h1 className="text-[28px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Olá{primeiroNome ? `, ${primeiroNome}` : ""}.
          </h1>
        </div>
      </header>

      <FiscalHealthScore />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ProximoPagamentoCard />
        <ProximaObrigacaoCard />
        <AlertasCard />
      </div>

      <QuickActions />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GraficoReceitaImposto />
        <CalendarioMesCard />
      </div>

      <div className="grid grid-cols-1 gap-4">
        <SimplesNacionalCard />
      </div>
    </div>
  );
}

function saudacao(d: Date): string {
  const h = d.getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}
