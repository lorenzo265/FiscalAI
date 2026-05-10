"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, Check, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import type { AnexoSimples, RegimeTributario } from "@/lib/schemas/empresa";
import { cn } from "@/lib/utils";
import { RegimeHelperModal } from "./regime-helper-modal";

interface RegimeOption {
  id: RegimeTributario;
  titulo: string;
  resumo: string;
  limite: string;
  destaque?: string;
}

const REGIMES: RegimeOption[] = [
  {
    id: "MEI",
    titulo: "MEI",
    resumo: "Microempreendedor individual. Imposto fixo, sem complicação.",
    limite: "Faturamento até R$ 81 mil/ano",
  },
  {
    id: "SIMPLES_NACIONAL",
    titulo: "Simples Nacional",
    resumo: "Vários impostos juntos em um pagamento mensal (DAS).",
    limite: "Faturamento até R$ 4,8 milhões/ano",
    destaque: "Mais comum em PMEs",
  },
  {
    id: "LUCRO_PRESUMIDO",
    titulo: "Lucro Presumido",
    resumo: "Impostos calculados sobre uma margem fixa, definida por lei.",
    limite: "Faturamento até R$ 78 milhões/ano",
  },
  {
    id: "LUCRO_REAL",
    titulo: "Lucro Real",
    resumo: "Impostos sobre o lucro contábil real. Mais controles, mais flexibilidade.",
    limite: "Acima de R$ 78 milhões ou setores específicos",
  },
];

const ANEXOS: { valor: AnexoSimples; titulo: string; descricao: string }[] = [
  {
    valor: "I",
    titulo: "Anexo I",
    descricao: "Comércio em geral — alíquotas começando em 4%.",
  },
  {
    valor: "II",
    titulo: "Anexo II",
    descricao: "Indústria — alíquotas a partir de 4,5%.",
  },
  {
    valor: "III",
    titulo: "Anexo III",
    descricao:
      "Serviços com folha de pagamento alta (Fator R ≥ 28%). Começa em 6%.",
  },
  {
    valor: "IV",
    titulo: "Anexo IV",
    descricao:
      "Serviços específicos: limpeza, vigilância, construção. Começa em 4,5% + INSS fora.",
  },
  {
    valor: "V",
    titulo: "Anexo V",
    descricao:
      "Serviços com folha baixa (Fator R < 28%). Alíquota inicial em 15,5%.",
  },
];

export function PassoRegime() {
  const regime = useOnboardingStore((s) => s.regime);
  const anexo = useOnboardingStore((s) => s.anexoSimples);
  const setRegime = useOnboardingStore((s) => s.setRegime);
  const setAnexo = useOnboardingStore((s) => s.setAnexoSimples);
  const setFat = useOnboardingStore((s) => s.setFaturamento12m);
  const proximo = useOnboardingStore((s) => s.proximo);
  const voltar = useOnboardingStore((s) => s.voltar);
  const [helperOpen, setHelperOpen] = React.useState(false);

  const podeAvancar = !!regime && (regime !== "SIMPLES_NACIONAL" || !!anexo);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {REGIMES.map((r) => {
          const ativo = regime === r.id;
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => setRegime(r.id)}
              className={cn(
                "text-left rounded-md border p-4 transition-all",
                ativo
                  ? "border-[var(--color-lime)] bg-[var(--color-lime-d)]"
                  : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-[var(--color-txt)]">
                    {r.titulo}
                  </span>
                  {r.destaque ? <Pill tom="info">{r.destaque}</Pill> : null}
                </div>
                {ativo ? (
                  <Check className="size-4 text-[var(--color-lime)]" />
                ) : null}
              </div>
              <p className="text-sm text-[var(--color-txt-2)] mt-1.5 leading-relaxed">
                {r.resumo}
              </p>
              <p className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-txt-3)] mt-3">
                {r.limite}
              </p>
            </button>
          );
        })}
      </div>

      {regime === "SIMPLES_NACIONAL" ? (
        <div className="flex flex-col gap-2">
          <p className="text-[11px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
            Qual anexo do Simples?
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {ANEXOS.map((a) => {
              const ativo = anexo === a.valor;
              return (
                <button
                  key={a.valor}
                  type="button"
                  onClick={() => setAnexo(a.valor)}
                  className={cn(
                    "text-left rounded-md border p-3 transition-all",
                    ativo
                      ? "border-[var(--color-blue)] bg-[var(--color-blue-d)]"
                      : "border-[var(--color-line-2)] bg-[var(--color-card-2)] hover:bg-[var(--color-card-3)]"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-[var(--color-txt)]">
                      {a.titulo}
                    </span>
                    {ativo ? (
                      <Check className="size-4 text-[var(--color-blue)]" />
                    ) : null}
                  </div>
                  <p className="text-xs text-[var(--color-txt-2)] mt-0.5 leading-snug">
                    {a.descricao}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3 pt-2">
        <button
          type="button"
          onClick={() => setHelperOpen(true)}
          className="flex items-center gap-1.5 text-xs text-[var(--color-blue)] hover:underline"
        >
          <HelpCircle className="size-3.5" />
          Não sei meu regime
        </button>

        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={voltar}>
            <ArrowLeft className="size-4" /> Voltar
          </Button>
          <Button onClick={proximo} disabled={!podeAvancar}>
            Continuar <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>

      <RegimeHelperModal
        open={helperOpen}
        onOpenChange={setHelperOpen}
        onSugerir={(r, fatAnual) => {
          setRegime(r);
          setFat(fatAnual);
          if (r === "SIMPLES_NACIONAL" && !anexo) setAnexo("III");
        }}
      />
    </div>
  );
}
