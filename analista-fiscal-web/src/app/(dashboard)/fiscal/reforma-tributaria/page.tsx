"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ArrowRight, Info, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Pill } from "@/components/shared/pill";
import { FiscalSubnav } from "@/components/fiscal/fiscal-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import {
  formatarMoeda,
  formatarMoedaCompacta,
} from "@/lib/format/moeda";

interface MarcoReforma {
  ano: number;
  titulo: string;
  descricao: string;
  destaque?: boolean;
}

const TIMELINE: MarcoReforma[] = [
  {
    ano: 2026,
    titulo: "Início do período de teste",
    descricao:
      "CBS começa em 0,9% e IBS em 0,1% — ainda compensáveis com PIS/Cofins.",
  },
  {
    ano: 2027,
    titulo: "PIS e Cofins extintos",
    descricao:
      "CBS sobe para alíquota cheia. Imposto Seletivo (IS) entra em vigor sobre itens nocivos.",
    destaque: true,
  },
  {
    ano: 2029,
    titulo: "Transição estadual começa",
    descricao:
      "Início da redução gradual de ICMS e ISS. IBS sobe na mesma proporção.",
  },
  {
    ano: 2032,
    titulo: "Último ano de ICMS/ISS",
    descricao:
      "Apuração paralela: você recolhe parte no antigo, parte no IBS.",
  },
  {
    ano: 2033,
    titulo: "Sistema novo 100% em vigor",
    descricao:
      "ICMS e ISS extintos. CBS + IBS substituem PIS, Cofins, IPI, ICMS e ISS.",
    destaque: true,
  },
];

interface ComparativoLinha {
  antes: string;
  depois: string;
  observacao: string;
}

const COMPARATIVO: ComparativoLinha[] = [
  {
    antes: "PIS + Cofins (federal)",
    depois: "CBS — Contribuição sobre Bens e Serviços",
    observacao: "Não cumulativo, com créditos amplos.",
  },
  {
    antes: "ICMS + ISS (estadual + municipal)",
    depois: "IBS — Imposto sobre Bens e Serviços",
    observacao:
      "Cobrado no destino, não na origem. Fim da guerra fiscal entre estados.",
  },
  {
    antes: "IPI",
    depois: "Imposto Seletivo (IS)",
    observacao:
      "Apenas sobre bens prejudiciais à saúde ou ambiente (cigarro, bebida, etc).",
  },
  {
    antes: "Múltiplas obrigações acessórias",
    depois: "Nota fiscal única + split payment",
    observacao:
      "Sistema fica responsável por separar o imposto na hora do pagamento.",
  },
];

export default function FiscalReformaTributariaPage() {
  const { empresa } = useEmpresaAtual();
  const fat = empresa?.faturamento12m ?? 850_000;

  const impostoAtualAprox = fat * 0.082;
  const impostoNovoAprox = fat * 0.094;
  const diferenca = impostoNovoAprox - impostoAtualAprox;
  const tendencia: "sobe" | "desce" | "neutro" =
    Math.abs(diferenca) < impostoAtualAprox * 0.02
      ? "neutro"
      : diferenca > 0
        ? "sobe"
        : "desce";

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo fiscal
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Reforma tributária 2026-2033
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
          A maior mudança fiscal em 60 anos. A gente acompanha pra você não ser
          pego de surpresa.
        </p>
      </header>

      <FiscalSubnav />

      <Card
        className="p-6 md:p-7 flex flex-col md:flex-row gap-5 items-start md:items-center"
        style={{ background: "var(--color-card)" }}
      >
        <div
          className="size-12 rounded-xl grid place-items-center shrink-0"
          style={{ background: "var(--color-blue-d)" }}
        >
          <Sparkles className="size-5" style={{ color: "var(--color-blue)" }} />
        </div>
        <div className="flex flex-col gap-1 flex-1">
          <Pill tom="info">Em vigor a partir de 2026</Pill>
          <h2 className="text-xl md:text-2xl font-extrabold text-[var(--color-txt)] tracking-tight leading-tight mt-1">
            A partir de 2026, o sistema tributário muda.
          </h2>
          <p className="text-sm text-[var(--color-txt-2)] max-w-2xl leading-relaxed">
            PIS, Cofins, IPI, ICMS e ISS deixam de existir. No lugar entram CBS
            (federal) e IBS (estadual + municipal). Simulamos o impacto na sua
            empresa abaixo.
          </p>
        </div>
      </Card>

      <Card className="p-6 flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Linha do tempo da transição
          </span>
        </div>
        <ol className="flex flex-col gap-0">
          {TIMELINE.map((m, i) => (
            <li key={m.ano} className="grid grid-cols-[80px_1fr] gap-4 relative">
              <div className="flex flex-col items-center pt-0.5">
                <span
                  className={
                    "mono text-[12px] font-bold py-1 px-2 rounded-md " +
                    (m.destaque
                      ? "bg-[var(--color-lime-d)] text-[var(--color-lime)]"
                      : "bg-[var(--color-card-2)] text-[var(--color-txt-2)]")
                  }
                >
                  {m.ano}
                </span>
                {i < TIMELINE.length - 1 ? (
                  <span
                    className="w-px flex-1 my-1"
                    style={{ background: "var(--color-line-2)" }}
                  />
                ) : null}
              </div>
              <div className="pb-5 flex flex-col gap-1">
                <span className="text-sm font-semibold text-[var(--color-txt)]">
                  {m.titulo}
                </span>
                <p className="text-[12px] text-[var(--color-txt-2)] leading-relaxed max-w-2xl">
                  {m.descricao}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Impacto estimado pra você
            </span>
            <Pill
              tom={
                tendencia === "sobe"
                  ? "warn"
                  : tendencia === "desce"
                    ? "ok"
                    : "neutral"
              }
            >
              {tendencia === "sobe"
                ? "tende a subir"
                : tendencia === "desce"
                  ? "tende a cair"
                  : "neutro"}
            </Pill>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <BlocoImpacto
              label="Cenário atual"
              valor={impostoAtualAprox}
              detalhe="PIS + Cofins + ICMS/ISS estimados."
            />
            <BlocoImpacto
              label="Cenário pós-reforma"
              valor={impostoNovoAprox}
              detalhe="CBS + IBS · alíquota cheia."
              destaque
            />
          </div>

          <div
            className="rounded-md border p-3 flex items-center gap-3"
            style={{
              background: "var(--color-card-2)",
              borderColor: "var(--color-line-2)",
            }}
          >
            {tendencia === "sobe" ? (
              <ArrowUp className="size-4 text-[var(--color-amber)]" />
            ) : tendencia === "desce" ? (
              <ArrowDown className="size-4 text-[var(--color-lime)]" />
            ) : (
              <ArrowRight className="size-4 text-[var(--color-txt-2)]" />
            )}
            <div className="flex flex-col">
              <span className="text-[11px] uppercase mono tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
                Diferença anual estimada
              </span>
              <span
                className="mono text-lg font-bold"
                style={{
                  color:
                    tendencia === "sobe"
                      ? "var(--color-amber)"
                      : tendencia === "desce"
                        ? "var(--color-lime)"
                        : "var(--color-txt)",
                }}
              >
                {diferenca >= 0 ? "+" : "-"}
                {formatarMoedaCompacta(Math.abs(diferenca))}
              </span>
            </div>
          </div>

          <p className="flex items-start gap-2 text-[11px] text-[var(--color-txt-3)] leading-snug">
            <Info className="size-3.5 mt-0.5 shrink-0" />
            Estimativa simplificada baseada em alíquotas cheias e faturamento de{" "}
            <span className="mono text-[var(--color-txt-2)] mx-1">
              {formatarMoeda(fat)}
            </span>
            . O número final depende do split de receita por estado/atividade.
          </p>
        </Card>

        <Card className="p-6 flex flex-col gap-3">
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            Antes vs depois
          </span>
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono"
                  style={{ borderColor: "var(--color-line)" }}
                >
                  <th className="py-2 px-1 font-bold">Hoje</th>
                  <th className="py-2 px-1 font-bold">Depois</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--color-line)" }}>
                {COMPARATIVO.map((c, i) => (
                  <tr
                    key={i}
                    className="border-t"
                    style={{ borderColor: "var(--color-line)" }}
                  >
                    <td className="py-3 px-1 align-top">
                      <span className="text-[var(--color-txt-2)] line-through decoration-[var(--color-txt-3)]">
                        {c.antes}
                      </span>
                    </td>
                    <td className="py-3 px-1 align-top">
                      <span className="text-[var(--color-txt)] font-medium block">
                        {c.depois}
                      </span>
                      <span className="text-[11px] text-[var(--color-txt-3)] leading-snug block mt-0.5">
                        {c.observacao}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

function BlocoImpacto({
  label,
  valor,
  detalhe,
  destaque,
}: {
  label: string;
  valor: number;
  detalhe: string;
  destaque?: boolean;
}) {
  return (
    <div
      className="rounded-md border p-3 flex flex-col gap-1"
      style={{
        background: destaque ? "var(--color-card-2)" : "transparent",
        borderColor: destaque
          ? "rgba(163,255,107,0.18)"
          : "var(--color-line-2)",
      }}
    >
      <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)]">
        {label}
      </span>
      <span className="mono text-2xl font-extrabold text-[var(--color-txt)] leading-none">
        {formatarMoedaCompacta(valor)}
      </span>
      <span className="text-[11px] text-[var(--color-txt-3)] leading-snug">
        {detalhe}
      </span>
    </div>
  );
}
