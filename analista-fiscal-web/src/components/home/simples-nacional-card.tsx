"use client";

import { Gauge } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { Progress } from "@/components/ui/progress";
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
    <Card className="p-5 flex flex-col gap-4 lg:col-span-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="size-4 text-[var(--color-lime)]" />
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Você no Simples Nacional
          </span>
        </div>
        {empresa?.anexoSimples ? (
          <Pill tom="ok">Anexo {empresa.anexoSimples}</Pill>
        ) : null}
      </div>

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
            descricao="Acima de R$ 4,8M você é excluída do regime."
            atual={fat}
            limite={teto}
            uso={usoTetoBp}
            tom={usoTetoBp < 70 ? "lime" : usoTetoBp < 90 ? "amber" : "red"}
          />
        </div>
      )}

      {data?.fatorR ? (
        <div
          className="rounded-md border p-3 flex items-center gap-3"
          style={{
            background: "var(--color-card-2)",
            borderColor: "var(--color-line-2)",
          }}
        >
          <span className="text-[10px] mono uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)]">
            Fator R
          </span>
          <span className="mono text-base font-bold text-[var(--color-txt)]">
            {(data.fatorR.valor * 100).toFixed(1).replace(".", ",")}%
          </span>
          <Pill tom={data.fatorR.atencao ? "warn" : "ok"}>
            {data.fatorR.atencao ? "atenção" : "anexo III mantido"}
          </Pill>
          <span className="ml-auto text-xs text-[var(--color-txt-2)]">
            Acima de 28% sua alíquota cai pela metade.
          </span>
        </div>
      ) : null}
    </Card>
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
        <span className="text-sm font-semibold text-[var(--color-txt)]">{titulo}</span>
        <span className="mono text-xs text-[var(--color-txt-2)]">{uso}%</span>
      </div>
      <Progress value={uso} tom={tom} />
      <div className="flex items-baseline justify-between text-xs text-[var(--color-txt-2)]">
        <span>
          <Moeda valor={atual} />
        </span>
        <span className="text-[var(--color-txt-3)]">
          de <Moeda valor={limite} />
        </span>
      </div>
      <p className="text-[11px] text-[var(--color-txt-3)] leading-snug">{descricao}</p>
    </div>
  );
}
