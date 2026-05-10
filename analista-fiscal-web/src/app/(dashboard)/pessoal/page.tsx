"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Plus,
  Users,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { AvatarFuncionario } from "@/components/pessoal/avatar-funcionario";
import { StatusFuncionarioPill } from "@/components/pessoal/status-funcionario-pill";
import {
  useEventosEsocial,
  useFuncionarios,
  useHoleritesDoMes,
} from "@/hooks/use-pessoal";
import {
  TIPO_CONTRATO_LABEL,
  type Funcionario,
  type Holerite,
} from "@/lib/schemas/pessoal";
import { chaveCompetencia } from "@/lib/pessoal/calculo-folha";
import { formatarMesAnoBR } from "@/lib/format/data";

export default function PessoalResumoPage() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth() + 1;

  const {
    data: funcionarios,
    isLoading: loadF,
    isError: errF,
    refetch: refF,
  } = useFuncionarios();
  const {
    data: holerites,
    isLoading: loadH,
  } = useHoleritesDoMes(ano, mes);
  const { data: eventos } = useEventosEsocial();

  const holeritePorFuncionario = React.useMemo(() => {
    const map = new Map<string, Holerite>();
    for (const h of holerites ?? []) map.set(h.funcionarioId, h);
    return map;
  }, [holerites]);

  const totais = React.useMemo(() => {
    const lista = holerites ?? [];
    return {
      bruto: lista.reduce((s, h) => s + h.totalProventos, 0),
      liquido: lista.reduce((s, h) => s + h.totalLiquido, 0),
      inssEmpresa: lista.reduce((s, h) => s + h.inssEmpresa, 0),
      fgts: lista.reduce((s, h) => s + h.fgts, 0),
    };
  }, [holerites]);

  const competencia = chaveCompetencia(ano, mes);
  const eventosDoMes = (eventos ?? []).filter(
    (e) => e.competencia === competencia
  );
  const totalPendentes = eventosDoMes.filter(
    (e) => e.status === "pendente" || e.status === "rascunho"
  ).length;
  const totalErros = eventosDoMes.filter((e) => e.status === "erro").length;
  const totalTransmitidos = eventosDoMes.filter(
    (e) => e.status === "transmitido"
  ).length;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <span className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-txt-3)] font-bold">
            Pessoal · Resumo
          </span>
          <h1 className="text-[26px] md:text-3xl font-extrabold tracking-tight text-[var(--color-txt)]">
            Folha de {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}
          </h1>
          <p className="text-sm text-[var(--color-txt-2)] max-w-2xl mt-1">
            Tudo que você precisa pra fechar a folha do mês: salários
            calculados, encargos provisionados e eventos do eSocial prontos
            pra transmitir.
          </p>
        </div>
        <Button asChild>
          <Link href="/pessoal/funcionarios/novo">
            <Plus className="size-4" /> Admitir funcionário
          </Link>
        </Button>
      </header>

      <PessoalSubnav />

      {totalErros > 0 ? (
        <Alert variant="warn" className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0" />
            <div>
              <AlertTitle>
                {totalErros} evento{totalErros > 1 ? "s" : ""} eSocial com
                erro
              </AlertTitle>
              <AlertDescription>
                A Receita rejeitou um envio. Corrija agora pra evitar multa por
                fechamento atrasado.
              </AlertDescription>
            </div>
          </div>
          <Button asChild className="shrink-0">
            <Link href="/pessoal/esocial">
              Resolver eventos <ArrowRight className="size-4" />
            </Link>
          </Button>
        </Alert>
      ) : null}

      {loadF || loadH ? (
        <LoadingState titulo="Calculando folha do mês..." />
      ) : errF ? (
        <ErrorState onTentarNovamente={() => void refF()} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label="Total bruto"
              valor={<Moeda valor={totais.bruto} />}
              sub={`${(holerites ?? []).length} holerites`}
            />
            <StatCard
              label="Total líquido"
              valor={<Moeda valor={totais.liquido} />}
              pill={{ tom: "ok", texto: "a pagar" }}
            />
            <StatCard
              label="INSS patronal"
              valor={<Moeda valor={totais.inssEmpresa} />}
              sub="20% + RAT + Terceiros"
            />
            <StatCard
              label="FGTS"
              valor={<Moeda valor={totais.fgts} />}
              sub="8% sobre folha CLT"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Card className="md:col-span-2 p-5 flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
                  Funcionários
                </span>
                <Button asChild variant="ghost" className="text-xs">
                  <Link href="/pessoal/funcionarios">
                    Ver todos <ArrowRight className="size-3.5" />
                  </Link>
                </Button>
              </div>

              {(funcionarios ?? []).length === 0 ? (
                <EmptyState
                  titulo="Nenhum funcionário cadastrado"
                  descricao="Cadastre seu primeiro funcionário pra começar a gerar holerites."
                  icone={Users}
                  acao={
                    <Button asChild>
                      <Link href="/pessoal/funcionarios/novo">
                        <Plus className="size-4" /> Admitir funcionário
                      </Link>
                    </Button>
                  }
                />
              ) : (
                <ul
                  className="divide-y -mx-2"
                  style={{ borderColor: "var(--color-line)" }}
                >
                  {(funcionarios ?? []).map((f) => (
                    <LinhaFuncionario
                      key={f.id}
                      funcionario={f}
                      holerite={holeritePorFuncionario.get(f.id)}
                    />
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                {totalErros === 0 && totalPendentes === 0 ? (
                  <CheckCircle2 className="size-4 text-[var(--color-lime)]" />
                ) : (
                  <AlertTriangle className="size-4 text-[var(--color-amber)]" />
                )}
                <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
                  eSocial · {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}
                </span>
              </div>

              <div className="flex flex-col gap-2">
                <ResumoLinha
                  texto="Eventos transmitidos"
                  valor={totalTransmitidos}
                  tom="ok"
                />
                <ResumoLinha
                  texto="Pendentes"
                  valor={totalPendentes}
                  tom={totalPendentes > 0 ? "warn" : "neutral"}
                />
                <ResumoLinha
                  texto="Com erro"
                  valor={totalErros}
                  tom={totalErros > 0 ? "error" : "neutral"}
                />
              </div>

              <Button asChild variant="outline" className="self-start">
                <Link href="/pessoal/esocial">Abrir painel eSocial</Link>
              </Button>
            </Card>
          </div>

          <Card className="p-5 flex flex-col md:flex-row md:items-center gap-3 justify-between">
            <div>
              <p className="text-sm font-semibold text-[var(--color-txt)]">
                Pronto pra fechar a folha?
              </p>
              <p className="text-xs text-[var(--color-txt-2)]">
                Reveja os holerites, transmita o eSocial e arquive os recibos.
              </p>
            </div>
            <Button asChild>
              <Link href={`/pessoal/folha/${ano}/${mes}`}>
                Abrir folha de {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)} <ArrowRight className="size-4" />
              </Link>
            </Button>
          </Card>
        </>
      )}
    </div>
  );
}

function LinhaFuncionario({
  funcionario,
  holerite,
}: {
  funcionario: Funcionario;
  holerite?: Holerite;
}) {
  return (
    <li className="px-2 py-2.5 flex items-center gap-3">
      <AvatarFuncionario nome={funcionario.nome} seed={funcionario.avatarSeed} />
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm font-semibold text-[var(--color-txt)] truncate">
          {funcionario.nome}
        </span>
        <span className="text-[11px] text-[var(--color-txt-3)] truncate">
          {funcionario.cargo} · {TIPO_CONTRATO_LABEL[funcionario.tipoContrato]}
        </span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <StatusFuncionarioPill status={funcionario.status} />
        <span className="mono text-sm font-bold text-[var(--color-txt)]">
          <Moeda valor={holerite?.totalLiquido ?? funcionario.salario} />
        </span>
        {holerite ? (
          <Pill tom={holerite.status === "pago" ? "ok" : "info"}>
            {holerite.status === "pago" ? "pago" : "gerado"}
          </Pill>
        ) : (
          <Pill tom="neutral">sem holerite</Pill>
        )}
      </div>
    </li>
  );
}

function ResumoLinha({
  texto,
  valor,
  tom,
}: {
  texto: string;
  valor: number;
  tom: "ok" | "warn" | "error" | "neutral";
}) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-[var(--color-txt-2)]">{texto}</span>
      <Pill tom={tom}>{valor}</Pill>
    </div>
  );
}
