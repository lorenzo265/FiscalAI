"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Plus, Search, Users } from "lucide-react";
import { useQueryStates, parseAsString } from "nuqs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { PessoalSubnav } from "@/components/pessoal/pessoal-subnav";
import { AvatarFuncionario } from "@/components/pessoal/avatar-funcionario";
import { StatusFuncionarioPill } from "@/components/pessoal/status-funcionario-pill";
import { useFuncionarios } from "@/hooks/use-pessoal";
import {
  TIPO_CONTRATO_LABEL,
  type Funcionario,
} from "@/lib/schemas/pessoal";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

export default function FuncionariosPage() {
  const { data, isLoading, isError, refetch } = useFuncionarios();
  const reduced = useReducedMotion();

  const [filtros, setFiltros] = useQueryStates(
    {
      q: parseAsString.withDefault(""),
      status: parseAsString.withDefault("todos"),
      contrato: parseAsString.withDefault("todos"),
    },
    { history: "replace" }
  );

  const lista = React.useMemo(() => {
    if (!data) return [];
    const q = filtros.q.trim().toLowerCase();
    return data.filter((f) => {
      if (filtros.status !== "todos" && f.status !== filtros.status) return false;
      if (filtros.contrato !== "todos" && f.tipoContrato !== filtros.contrato)
        return false;
      if (
        q &&
        !f.nome.toLowerCase().includes(q) &&
        !f.cargo.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [data, filtros]);

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
            Pessoal · Funcionários
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-serif text-[28px] md:text-[32px] tracking-tight text-[var(--color-ink)] leading-tight"
          >
            Funcionários
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-xl mt-1"
          >
            Quem está ativo, afastado ou desligado. Uma admissão aqui gera o
            evento{" "}
            <abbr
              title="S-2200 — Cadastramento Inicial do Vínculo Trabalhista"
              className="mono text-[11px] text-[var(--color-ink-2)] no-underline"
            >
              S-2200
            </abbr>{" "}
            no eSocial automaticamente.
          </motion.p>
        </div>
        <motion.div variants={itemV} className="shrink-0">
          <Button asChild size="default" className="h-11 px-5 gap-2">
            <Link href="/pessoal/funcionarios/novo">
              <Plus className="size-4" /> Admitir funcionário
            </Link>
          </Button>
        </motion.div>
      </motion.header>

      <PessoalSubnav />

      {/* ── filtros ── */}
      <Framed
        marks={false}
        tone="rule"
        surface="card"
        className="flex flex-col md:flex-row md:items-center gap-3"
      >
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
          <Input
            value={filtros.q}
            onChange={(e) => void setFiltros({ q: e.target.value })}
            placeholder="Buscar por nome ou cargo"
            className="pl-9"
          />
        </div>
        <Select
          value={filtros.status}
          onValueChange={(v) => void setFiltros({ status: v })}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os status</SelectItem>
            <SelectItem value="ativo">Ativos</SelectItem>
            <SelectItem value="afastado">Afastados</SelectItem>
            <SelectItem value="demitido">Demitidos</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filtros.contrato}
          onValueChange={(v) => void setFiltros({ contrato: v })}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os contratos</SelectItem>
            <SelectItem value="CLT">CLT</SelectItem>
            <SelectItem value="PJ">PJ (prestador)</SelectItem>
            <SelectItem value="ESTAGIO">Estágio</SelectItem>
          </SelectContent>
        </Select>
      </Framed>

      {/* ── conteúdo principal ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando funcionários..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : lista.length === 0 ? (
        <EmptyState
          titulo="Nenhum funcionário"
          descricao="Cadastre seu primeiro funcionário para começar."
          icone={Users}
          acao={
            <Button asChild>
              <Link href="/pessoal/funcionarios/novo">
                <Plus className="size-4" /> Admitir
              </Link>
            </Button>
          }
        />
      ) : (
        <Framed marks={false} tone="rule" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-3 border-b border-[var(--color-rule)]">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-2)]">
              Cadastro de funcionários
            </h2>
          </div>
          <ul className="divide-y" style={{ borderColor: "var(--color-rule)" }}>
            {lista.map((f) => (
              <LinhaFuncionario key={f.id} funcionario={f} />
            ))}
          </ul>
          <div className="px-5 py-3 border-t border-[var(--color-rule)]">
            <span
              className="text-xs text-[var(--color-ink-2)] mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {lista.length} funcionário{lista.length !== 1 ? "s" : ""}
            </span>
          </div>
        </Framed>
      )}
    </motion.div>
  );
}

function LinhaFuncionario({ funcionario }: { funcionario: Funcionario }) {
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <AvatarFuncionario
          nome={funcionario.nome}
          seed={funcionario.avatarSeed}
          size="lg"
        />
        <div className="min-w-0">
          <span className="text-sm font-semibold text-[var(--color-ink)] truncate block">
            {funcionario.nome}
          </span>
          <span className="text-[11px] text-[var(--color-ink-2)] truncate block">
            {funcionario.cargo} · {TIPO_CONTRATO_LABEL[funcionario.tipoContrato]}{" "}
            · admitido{" "}
            <span className="mono" style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatarDataBR(funcionario.dataAdmissao)}
            </span>
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <StatusFuncionarioPill status={funcionario.status} />
        <span
          className="mono text-base font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={funcionario.salario} />
        </span>
      </div>
    </li>
  );
}
