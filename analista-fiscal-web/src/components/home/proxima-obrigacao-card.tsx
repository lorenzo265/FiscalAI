"use client";

import Link from "next/link";
import { ArrowRight, FileSignature } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Skeleton } from "@/components/ui/skeleton";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { useFiscalSaude } from "@/hooks/use-fiscal-saude";
import { formatarDataBR } from "@/lib/format/data";
import { traduzirObrigacao } from "@/lib/traducao/obrigacoes";
import { classificarUrgencia } from "@/lib/urgencia";

/**
 * Tenta traduzir o título de uma obrigação para PT claro.
 * Se não reconhecer, retorna o título original (nunca vaza sigla crua).
 */
function resolverObrigacao(titulo: string): { pt: string; sigla: string | null } {
  const candidatos = [
    "PGDAS-D", "PGDAS_D", "DEFIS", "DCTFWeb", "DCTF",
    "eSocial", "ESOCIAL", "DAS", "FGTS", "INSS", "GFIP",
  ];
  for (const token of candidatos) {
    if (titulo.toUpperCase().includes(token.toUpperCase())) {
      const entrada = traduzirObrigacao(token);
      if (entrada) return { pt: entrada.titulo, sigla: entrada.termoTecnico };
    }
  }
  return { pt: titulo, sigla: null };
}

export function ProximaObrigacaoCard() {
  const { data, isLoading } = useFiscalSaude();
  const obrig = data?.proximaObrigacao;
  const traduzido = obrig ? resolverObrigacao(obrig.titulo) : null;
  const urg = obrig ? classificarUrgencia(obrig.vencimento) : null;

  return (
    <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <FileSignature className="size-4 text-[var(--color-ochre)]" aria-hidden />
        <Fig n={2} titulo="Próxima obrigação" size="sm" />
        <Pill tom="warn" semIcone>declaração</Pill>
      </div>
      {isLoading || !obrig || !traduzido ? (
        <>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </>
      ) : (
        <>
          {/* título PT + sigla técnica em abbr */}
          <p className="text-lg font-semibold text-[var(--color-ink)] leading-tight">
            {traduzido.pt}
            {traduzido.sigla ? (
              <>
                {" "}
                <abbr
                  title={traduzido.sigla}
                  className="mono text-sm font-normal text-[var(--color-ink-3)] no-underline"
                >
                  {traduzido.sigla}
                </abbr>
              </>
            ) : null}
          </p>
          <p className="text-sm text-[var(--color-ink-2)] leading-relaxed">
            {obrig.descricao}
          </p>
          <p
            className="text-xs mono"
            style={{
              color:
                urg && urg.nivel !== "neutro"
                  ? urg.nivel === "danger"
                    ? "var(--color-danger)"
                    : "var(--color-ochre)"
                  : "var(--color-ink-3)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            até {formatarDataBR(obrig.vencimento)}
            {urg && urg.nivel !== "neutro" ? <> · <strong>{urg.rotulo}</strong></> : null}
          </p>
        </>
      )}
      {obrig ? (
        <Button asChild variant="outline" size="sm" className="self-start mt-1">
          <Link href={obrig.acao.rota}>
            {obrig.acao.label}
            <ArrowRight className="size-3.5" />
          </Link>
        </Button>
      ) : null}
    </Framed>
  );
}
