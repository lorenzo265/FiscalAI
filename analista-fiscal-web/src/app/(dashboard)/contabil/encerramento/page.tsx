"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowUp,
  CalendarCheck,
  CheckCircle2,
  Loader2,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { LoadingState } from "@/components/shared/loading-state";
import { ContabilSubnav } from "@/components/contabil/contabil-subnav";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useLancamentos } from "@/hooks/use-contabil";
import { calcularResultadoExercicio } from "@/lib/contabil/motor";
import { formatarMoeda } from "@/lib/format/moeda";

const NOMES_MES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

type Estado = "pronto" | "fechando" | "fechado";

export default function EncerramentoPage() {
  const { empresa } = useEmpresaAtual();
  const { data: lancamentos, isLoading } = useLancamentos();
  const hoje = React.useMemo(() => new Date(), []);
  const mesRef = hoje.getMonth() === 0 ? 12 : hoje.getMonth();
  const anoRef = hoje.getMonth() === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();

  const lancamentosMes = React.useMemo(() => {
    if (!lancamentos) return [];
    return lancamentos.filter((l) => {
      const d = new Date(l.data);
      return d.getFullYear() === anoRef && d.getMonth() + 1 === mesRef;
    });
  }, [lancamentos, anoRef, mesRef]);

  const resultado = React.useMemo(
    () => calcularResultadoExercicio(lancamentosMes),
    [lancamentosMes]
  );

  const [estado, setEstado] = React.useState<Estado>("pronto");

  const fechar = async () => {
    setEstado("fechando");
    await new Promise((r) => setTimeout(r, 2_400));
    setEstado("fechado");
    toast.success("Mês encerrado", {
      description: `Resultado de ${NOMES_MES[mesRef - 1]}/${anoRef} apurado e distribuído.`,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
          Módulo contábil
        </span>
        <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
          Encerramento do exercício
        </h1>
        <p className="text-sm text-[var(--color-txt-2)] max-w-xl mt-1">
          Apura o resultado do mês, transfere pra Lucros Acumulados e
          consolida o balancete.
        </p>
      </header>

      <ContabilSubnav />

      {isLoading ? (
        <LoadingState titulo="Lendo movimentação do mês..." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
          <Card className="p-6 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <CalendarCheck className="size-4 text-[var(--color-blue)]" />
                <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
                  Período de referência
                </span>
              </div>
              <Pill tom={estado === "fechado" ? "ok" : "info"}>
                {estado === "fechado" ? "encerrado" : "em aberto"}
              </Pill>
            </div>
            <h2 className="text-2xl font-extrabold text-[var(--color-txt)] tracking-tight capitalize">
              {NOMES_MES[mesRef - 1]} de {anoRef}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <BlocoResultado
                label="Receitas"
                valor={resultado.receita}
                icon={ArrowUp}
                cor="var(--color-lime)"
              />
              <BlocoResultado
                label="Despesas"
                valor={resultado.despesa}
                icon={ArrowDown}
                cor="var(--color-amber)"
              />
              <BlocoResultado
                label="Resultado"
                valor={resultado.resultado}
                icon={Sparkles}
                cor={
                  resultado.resultado >= 0
                    ? "var(--color-lime)"
                    : "var(--color-red)"
                }
                destaque
              />
            </div>

            {estado === "pronto" ? (
              <Button
                size="lg"
                className="self-start mt-2"
                onClick={fechar}
                disabled={lancamentosMes.length === 0}
              >
                Fechar {NOMES_MES[mesRef - 1]}/{anoRef}
              </Button>
            ) : null}

            {estado === "fechando" ? (
              <div
                className="rounded-md border p-4 flex items-center gap-3"
                style={{
                  background: "var(--color-card-2)",
                  borderColor: "var(--color-line-2)",
                }}
              >
                <Loader2 className="size-5 animate-spin text-[var(--color-lime)]" />
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-[var(--color-txt)]">
                    Apurando resultado do exercício...
                  </span>
                  <span className="text-[12px] text-[var(--color-txt-3)]">
                    Transferindo saldos de receita e despesa para Lucros
                    Acumulados.
                  </span>
                </div>
              </div>
            ) : null}

            {estado === "fechado" ? (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-md border p-4 flex items-start gap-3"
                style={{
                  background: "var(--color-lime-d)",
                  borderColor: "rgba(163,255,107,0.32)",
                }}
              >
                <CheckCircle2 className="size-5 text-[var(--color-lime)] mt-0.5" />
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-semibold text-[var(--color-txt)]">
                    {NOMES_MES[mesRef - 1]}/{anoRef} encerrado
                  </span>
                  <p className="text-[13px] text-[var(--color-txt-2)] leading-relaxed">
                    Resultado do exercício:{" "}
                    <strong
                      className="mono"
                      style={{
                        color:
                          resultado.resultado >= 0
                            ? "var(--color-lime)"
                            : "var(--color-red)",
                      }}
                    >
                      {resultado.resultado >= 0 ? "Lucro" : "Prejuízo"} de{" "}
                      <Moeda valor={Math.abs(resultado.resultado)} />
                    </strong>
                    .{" "}
                    {resultado.resultado >= 0
                      ? "Distribuído conforme contrato social — Lucros Acumulados (3.2.1)."
                      : "Mantido em Prejuízos Acumulados para compensação futura."}
                  </p>
                </div>
              </motion.div>
            ) : null}
          </Card>

          <Card className="p-5 flex flex-col gap-3 self-start">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              O que acontece quando você fecha
            </span>
            <ol className="flex flex-col gap-3 text-[13px] text-[var(--color-txt-2)] leading-relaxed">
              <Passo
                n={1}
                titulo="Apuração do resultado"
                descricao="Sistema soma todas as contas de receita (4) e despesa (5) do período."
              />
              <Passo
                n={2}
                titulo="Transferência pra PL"
                descricao="O saldo é jogado em Lucros Acumulados (3.2.1), zerando receitas e despesas pro próximo exercício."
              />
              <Passo
                n={3}
                titulo="Consolidação"
                descricao="Balancete fica congelado — qualquer ajuste depois exige reabertura."
              />
            </ol>

            <div
              className="rounded-md border p-3 mt-2 text-[11px] text-[var(--color-txt-3)] leading-snug"
              style={{
                background: "var(--color-card-2)",
                borderColor: "var(--color-line-2)",
              }}
            >
              {empresa?.razaoSocial ?? "Empresa"} · CNPJ{" "}
              {empresa?.cnpj ?? "—"} · responsável técnico:
              demonstração FiscalAI.
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function BlocoResultado({
  label,
  valor,
  icon: Icon,
  cor,
  destaque,
}: {
  label: string;
  valor: number;
  icon: typeof ArrowUp;
  cor: string;
  destaque?: boolean;
}) {
  return (
    <div
      className="rounded-md border p-3 flex flex-col gap-1.5"
      style={{
        background: destaque ? "var(--color-card-2)" : "transparent",
        borderColor: destaque ? cor : "var(--color-line-2)",
      }}
    >
      <div className="flex items-center gap-1.5">
        <Icon className="size-3.5" style={{ color: cor }} />
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
          {label}
        </span>
      </div>
      <span
        className="mono font-extrabold leading-none"
        style={{ color: cor, fontSize: destaque ? 28 : 22 }}
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}

function Passo({
  n,
  titulo,
  descricao,
}: {
  n: number;
  titulo: string;
  descricao: string;
}) {
  return (
    <li className="flex gap-3">
      <span
        className="size-6 rounded-full grid place-items-center mono text-[11px] font-bold shrink-0"
        style={{
          background: "var(--color-lime-d)",
          color: "var(--color-lime)",
        }}
      >
        {n}
      </span>
      <div className="flex flex-col gap-0.5">
        <span className="text-[var(--color-txt)] font-semibold">{titulo}</span>
        <span className="text-[var(--color-txt-3)] leading-snug">
          {descricao}
        </span>
      </div>
    </li>
  );
}
