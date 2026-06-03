"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Plus,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
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
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function PessoalResumoPage() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth() + 1;
  const reduced = useReducedMotion();

  const {
    data: funcionarios,
    isLoading: loadF,
    isError: errF,
    refetch: refF,
  } = useFuncionarios();
  const { data: holerites, isLoading: loadH } = useHoleritesDoMes(ano, mes);
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

  const containerV = reduced ? staticVariants : staggerChildren;
  const itemV = reduced ? staticVariants : revealChild;
  const pageV = reduced ? staticVariants : reveal;

  return (
    <motion.div
      className="flex flex-col gap-6"
      variants={pageV}
      initial="hidden"
      animate="show"
    >
      {/* ── cabeçalho ── */}
      <motion.header
        className="flex items-end justify-between gap-3 flex-wrap"
        variants={containerV}
        initial="hidden"
        animate="show"
      >
        <div>
          <motion.span
            variants={itemV}
            className="text-[10px] mono uppercase tracking-[0.18em] text-[var(--color-ink-3)] font-bold block"
          >
            Módulo · Pessoal
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-[family-name:var(--font-serif)] text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
          >
            Folha de{" "}
            {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Salários calculados, encargos provisionados e eventos do eSocial
            prontos para transmitir.
          </motion.p>
        </div>
        <motion.div variants={itemV}>
          <Button asChild>
            <Link href="/pessoal/funcionarios/novo">
              <Plus className="size-4" /> Admitir funcionário
            </Link>
          </Button>
        </motion.div>
      </motion.header>

      <PessoalSubnav />

      {/* ── alerta de erros ── */}
      {totalErros > 0 ? (
        <Framed
          marks={false}
          tone="rule"
          surface="paper-2"
          className="flex flex-col md:flex-row md:items-center gap-3"
          style={{ borderColor: "var(--color-danger)" }}
        >
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="size-4 mt-0.5 shrink-0 text-[var(--color-danger)]" />
            <div>
              <p className="text-sm font-semibold text-[var(--color-ink)]">
                {totalErros} evento{totalErros > 1 ? "s" : ""} eSocial com
                erro
              </p>
              <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
                A Receita rejeitou um envio. Corrija agora para evitar multa
                por fechamento atrasado.
              </p>
            </div>
          </div>
          <Button asChild className="shrink-0" size="sm">
            <Link href="/pessoal/esocial">
              Resolver eventos <ArrowRight className="size-4" />
            </Link>
          </Button>
        </Framed>
      ) : null}

      {loadF || loadH ? (
        <LoadingState titulo="Calculando folha do mês..." />
      ) : errF ? (
        <ErrorState onTentarNovamente={() => void refF()} />
      ) : (
        <>
          {/* ── totais ── */}
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
            {/* ── lista de funcionários ── */}
            <Framed
              marks
              tone="ink"
              surface="card"
              padded={false}
              className="md:col-span-2 overflow-hidden"
            >
              <div className="px-5 pt-4 pb-2 flex items-center justify-between gap-2">
                <Fig n={1} titulo="Funcionários" size="sm" />
                <Button asChild variant="ghost" size="sm" className="text-xs">
                  <Link href="/pessoal/funcionarios">
                    Ver todos <ArrowRight className="size-3.5" />
                  </Link>
                </Button>
              </div>
              <Ruler />

              {(funcionarios ?? []).length === 0 ? (
                <div className="p-5">
                  <EmptyState
                    titulo="Nenhum funcionário cadastrado"
                    descricao="Cadastre seu primeiro funcionário para começar a gerar holerites."
                    icone={Users}
                    acao={
                      <Button asChild size="sm">
                        <Link href="/pessoal/funcionarios/novo">
                          <Plus className="size-4" /> Admitir
                        </Link>
                      </Button>
                    }
                  />
                </div>
              ) : (
                <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
                  {(funcionarios ?? []).map((f) => (
                    <LinhaFuncionario
                      key={f.id}
                      funcionario={f}
                      holerite={holeritePorFuncionario.get(f.id)}
                    />
                  ))}
                </ul>
              )}
            </Framed>

            {/* ── resumo esocial ── */}
            <Framed marks={false} tone="rule" surface="card" className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                {totalErros === 0 && totalPendentes === 0 ? (
                  <CheckCircle2 className="size-4 text-[var(--color-green)] shrink-0" />
                ) : (
                  <AlertTriangle className="size-4 text-[var(--color-ochre)] shrink-0" />
                )}
                <Fig
                  n={2}
                  titulo={`eSocial · ${formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}`}
                  size="sm"
                />
              </div>

              <div className="flex flex-col gap-2">
                <ResumoLinha
                  texto="Transmitidos"
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

              <Button asChild variant="outline" size="sm" className="self-start">
                <Link href="/pessoal/esocial">Abrir painel eSocial</Link>
              </Button>
            </Framed>
          </div>

          {/* ── CTA fechar folha ── */}
          <Framed
            marks={false}
            tone="rule"
            surface="paper-2"
            className="flex flex-col md:flex-row md:items-center gap-3 justify-between"
          >
            <div>
              <p className="text-sm font-semibold text-[var(--color-ink)]">
                Pronto para fechar a folha?
              </p>
              <p className="text-xs text-[var(--color-ink-2)] mt-0.5">
                Reveja os holerites, transmita o eSocial e arquive os recibos.
              </p>
            </div>
            <Button asChild size="sm">
              <Link href={`/pessoal/folha/${ano}/${mes}`}>
                Abrir folha de{" "}
                {formatarMesAnoBR(`${ano}-${String(mes).padStart(2, "0")}-01`)}{" "}
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </Framed>
        </>
      )}
    </motion.div>
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
    <li className="px-5 py-3 flex items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <AvatarFuncionario nome={funcionario.nome} seed={funcionario.avatarSeed} />
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm font-semibold text-[var(--color-ink)] truncate">
          {funcionario.nome}
        </span>
        <span className="text-[11px] text-[var(--color-ink-3)] truncate">
          {funcionario.cargo} · {TIPO_CONTRATO_LABEL[funcionario.tipoContrato]}
        </span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <StatusFuncionarioPill status={funcionario.status} />
        <span
          className="mono text-sm font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
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
      <span className="text-[var(--color-ink-2)]">{texto}</span>
      <Pill tom={tom}>
        <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
          {valor}
        </span>
      </Pill>
    </div>
  );
}
