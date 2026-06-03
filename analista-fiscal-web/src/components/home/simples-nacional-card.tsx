"use client";

import { Gauge } from "lucide-react";
import { Pill } from "@/components/shared/pill";
import { Progress } from "@/components/ui/progress";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useApuracaoAtual } from "@/hooks/use-apuracao-atual";
import { Moeda } from "@/components/shared/moeda";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";

export function SimplesNacionalCard() {
  const { empresa } = useEmpresaAtual();
  const { data, isLoading } = useApuracaoAtual();

  if (empresa && empresa.regime !== "SIMPLES_NACIONAL") return null;

  const fat = data?.faturamento12m ?? empresa?.faturamento12m ?? 0;
  const sublimite = data?.sublimiteEstadual ?? 3_600_000;
  const teto = data?.tetoSimples ?? 4_800_000;
  const usoSubBp = Math.min(100, Math.round((fat / sublimite) * 100));
  const usoTetoBp = Math.min(100, Math.round((fat / teto) * 100));

  return (
    <Framed marks tone="rule" surface="card" padded={false} className="overflow-hidden lg:col-span-2">
      {/* cabeçalho */}
      <div className="flex items-center justify-between gap-2 px-5 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-green)]" aria-hidden />
          <Fig n={4} titulo="Simples Nacional — limites" size="sm" />
        </div>
        {empresa?.anexoSimples ? (
          <Pill tom="ok">Anexo {empresa.anexoSimples}</Pill>
        ) : null}
      </div>
      <Ruler />

      <div className="px-5 py-4">
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Linha
              titulo="Sublimite estadual"
              descricao="Limite para recolher ICMS dentro do Simples (R$ 3,6M/ano)."
              atual={fat}
              limite={sublimite}
              uso={usoSubBp}
              tom={usoSubBp < 70 ? "lime" : usoSubBp < 90 ? "amber" : "red"}
            />
            <Linha
              titulo="Teto do Simples"
              descricao="Acima de R$ 4,8M a empresa é excluída do regime."
              atual={fat}
              limite={teto}
              uso={usoTetoBp}
              tom={usoTetoBp < 70 ? "lime" : usoTetoBp < 90 ? "amber" : "red"}
            />
          </div>
        )}

        {data?.fatorR ? (
          <div
            className="mt-4 rounded-[var(--radius-md)] border p-3 flex items-center gap-3"
            style={{
              background: "var(--color-paper-2)",
              borderColor: "var(--color-rule-2)",
            }}
          >
            <span className="text-[10px] mono uppercase tracking-[0.16em] font-bold text-[var(--color-ink-3)]">
              Fator R
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
      </div>
    </Framed>
  );
}

function Linha({
  titulo,
  descricao,
  atual,
  limite,
  uso,
  tom,
}: {
  titulo: string;
  descricao: string;
  atual: number;
  limite: number;
  uso: number;
  tom: "lime" | "amber" | "red";
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-[var(--color-ink)]">{titulo}</span>
        <span
          className="mono text-xs text-[var(--color-ink-2)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {uso}%
        </span>
      </div>
      <Progress value={uso} tom={tom} />
      <div
        className="flex items-baseline justify-between text-xs text-[var(--color-ink-2)]"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        <span className="mono">
          <Moeda valor={atual} />
        </span>
        <span className="text-[var(--color-ink-2)]">
          de <Moeda valor={limite} />
        </span>
      </div>
      <p className="text-[11px] text-[var(--color-ink-3)] leading-snug">{descricao}</p>
    </div>
  );
}
