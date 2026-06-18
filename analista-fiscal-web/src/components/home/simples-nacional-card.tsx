"use client";

import { Gauge } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Framed } from "@/components/blueprint/framed";
import { RulerGauge } from "@/components/blueprint/ruler";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { Moeda } from "@/components/shared/moeda";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

/**
 * SimplesNacionalCard v2 — "Arkan Claro"
 *
 * Assinatura nº2 da home: RulerGauge para teto do Simples Nacional.
 * Sem crop marks (painel comum); painel plano tone="rule".
 *
 * Dados: faturamento12m vs. sublimite + teto (RulerGauge por linha).
 * Projeção: extrapolada linearmente do ritmo mensal atual.
 */

/** Calcula o mês em que o ritmo atual cruzará o limite. */
function projetarMesCruzamento(
  fatAtual: number,
  limite: number,
  mesAtual: number /* 0–11 */
): { valor: number; label: string } | null {
  if (fatAtual <= 0 || fatAtual >= limite) return null;
  // ritmo médio mensal (faturamento acumulado nos mesAtual+1 meses do ano)
  const mesesDecorridos = mesAtual + 1;
  const ritmoMensal = fatAtual / mesesDecorridos;
  if (ritmoMensal <= 0) return null;
  const mesesParaCruzar = Math.ceil((limite - fatAtual) / ritmoMensal);
  const mesCruzamento = mesAtual + mesesParaCruzar;
  if (mesCruzamento > 11) return null; // não cruza no ano corrente
  const valorProjetado = fatAtual + ritmoMensal * mesesParaCruzar;
  const label = new Intl.DateTimeFormat("pt-BR", { month: "short" }).format(
    new Date(new Date().getFullYear(), mesCruzamento, 1)
  );
  return { valor: valorProjetado, label: `no ritmo: ${label}` };
}

export function SimplesNacionalCard() {
  const { empresa } = useEmpresaAtual();
  const { data, isLoading } = useApuracaoAtual();

  if (empresa && empresa.regime !== "SIMPLES_NACIONAL") return null;

  const fat = data?.faturamento12m ?? empresa?.faturamento12m ?? 0;
  const sublimite = data?.sublimiteEstadual ?? 3_600_000;
  const teto = data?.tetoSimples ?? 4_800_000;
  const mesAtual = new Date().getMonth();

  /* ── projeção linear para cada limite ── */
  const projSub = projetarMesCruzamento(fat, sublimite, mesAtual);
  const projTeto = projetarMesCruzamento(fat, teto, mesAtual);

  /* ── rótulo de % usado ── */
  const pctSubBp = Math.min(100, Math.round((fat / sublimite) * 100));
  const pctTetoBp = Math.min(100, Math.round((fat / teto) * 100));

  return (
    /* Painel plano v2: marks=false, tone="rule" */
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-5">
      {/* cabeçalho */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-green)]" aria-hidden />
          <span className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
            Simples Nacional — limites
          </span>
        </div>
        {empresa?.anexoSimples ? (
          <Pill tom="ok">Anexo {empresa.anexoSimples}</Pill>
        ) : null}
      </div>

      {/* faturamento atual em destaque */}
      <div className="flex flex-col gap-0.5">
        <span className="mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-ink-3)] font-semibold">
          Faturamento acumulado (12 meses)
        </span>
        <span
          className="mono text-2xl font-semibold text-[var(--color-ink)] leading-tight"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {isLoading ? <Skeleton className="h-7 w-36 inline-block" /> : <Moeda valor={fat} />}
        </span>
      </div>

      {isLoading ? (
        <Skeleton className="h-20 w-full" />
      ) : (
        <div className="flex flex-col gap-5">
          {/* ── Régua 1: Sublimite estadual (assinatura nº2 — RulerGauge) ── */}
          <RulerGauge
            valor={fat}
            limite={sublimite}
            projecao={projSub?.valor}
            projecaoLabel={projSub?.label}
            label="Sublimite estadual"
            valorLabel={
              <>
                <Moeda valor={fat} /> / <Moeda valor={sublimite} />
                <span className="ml-2 text-[var(--color-ink-2)]">({pctSubBp}%)</span>
              </>
            }
          />

          {/* ── Régua 2: Teto do Simples ── */}
          <RulerGauge
            valor={fat}
            limite={teto}
            projecao={projTeto?.valor}
            projecaoLabel={projTeto?.label}
            label="Teto do Simples"
            valorLabel={
              <>
                <Moeda valor={fat} /> / <Moeda valor={teto} />
                <span className="ml-2 text-[var(--color-ink-2)]">({pctTetoBp}%)</span>
              </>
            }
          />

          {/* ── Fator R (condicional, quando disponível) ── */}
          {data?.fatorR ? (
            <div
              className="rounded-[var(--radius-md)] border p-3 flex items-center gap-3"
              style={{
                background: "var(--color-paper-2)",
                borderColor: "var(--color-rule-2)",
              }}
            >
              <span className="text-[10px] mono uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)]">
                <abbr title="Fator de proporcionalidade entre folha e faturamento">
                  Fator R
                </abbr>
              </span>
              <span
                className="mono text-base font-bold text-[var(--color-ink)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {(data.fatorR.valor * 100).toFixed(1).replace(".", ",")}%
              </span>
              <Pill tom={data.fatorR.atencao ? "warn" : "ok"}>
                {data.fatorR.atencao ? "atenção" : "Anexo III mantido"}
              </Pill>
              <span className="ml-auto text-xs text-[var(--color-ink-2)]">
                Acima de 28% a alíquota cai pela metade.
              </span>
            </div>
          ) : null}

          {/* notas de contexto */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <p className="text-[11px] text-[var(--color-ink-3)] leading-snug">
              Sublimite estadual: acima de{" "}
              <Moeda valor={sublimite} /> a empresa recolhe{" "}
              <abbr title="Imposto sobre Circulação de Mercadorias e Serviços">ICMS</abbr>{" "}
              fora do Simples.
            </p>
            <p className="text-[11px] text-[var(--color-ink-3)] leading-snug">
              Teto do Simples: acima de{" "}
              <Moeda valor={teto} /> a empresa é excluída do regime.
            </p>
          </div>
        </div>
      )}
    </Framed>
  );
}
