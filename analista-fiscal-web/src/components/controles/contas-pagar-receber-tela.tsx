"use client";

import * as React from "react";
import {
  Check,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { motion } from "framer-motion";
import { useQueryStates, parseAsString } from "nuqs";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LoadingState } from "@/components/shared/loading-state";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Moeda } from "@/components/shared/moeda";
import { StatCard } from "@/components/shared/stat-card";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { ControlesSubnav } from "@/components/controles/controles-subnav";
import { StatusContaPill } from "@/components/controles/status-conta-pill";
import { ContaFormDialog } from "@/components/controles/conta-form-dialog";
import {
  useAdicionarContaPagarReceber,
  useAtualizarContaPagarReceber,
  useContasPagarReceber,
  useMarcarContaPaga,
  useRemoverContaPagarReceber,
} from "@/hooks/use-controles";
import {
  CATEGORIA_CONTA_LABEL,
  type ContaPagarReceber,
  type StatusContaPagarReceber,
  type TipoContaPagarReceber,
} from "@/lib/schemas/controles";
import { formatarDataBR } from "@/lib/format/data";
import {
  reveal,
  staggerChildren,
  revealChild,
  staticVariants,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";

interface Props {
  tipo: TipoContaPagarReceber;
}

export function ContasPagarReceberTela({ tipo }: Props) {
  const { data, isLoading, isError, refetch } = useContasPagarReceber();
  const adicionar = useAdicionarContaPagarReceber();
  const atualizar = useAtualizarContaPagarReceber();
  const remover = useRemoverContaPagarReceber();
  const marcarPaga = useMarcarContaPaga();
  const reduced = useReducedMotion();

  const [filtros, setFiltros] = useQueryStates(
    {
      q: parseAsString.withDefault(""),
      status: parseAsString.withDefault("todos"),
      vencimento: parseAsString.withDefault("60d"),
    },
    { history: "replace" }
  );

  const [abertoForm, setAbertoForm] = React.useState(false);
  const [editando, setEditando] = React.useState<ContaPagarReceber | null>(null);
  const [confirmandoRemocao, setConfirmandoRemocao] =
    React.useState<ContaPagarReceber | null>(null);

  const titulo = tipo === "pagar" ? "Contas a pagar" : "Contas a receber";
  const palavraAcao = tipo === "pagar" ? "pagar" : "receber";

  const lista = React.useMemo(() => {
    if (!data) return [];
    const corte = corteDataDias(filtros.vencimento);
    const q = filtros.q.trim().toLowerCase();
    return data.filter((c) => {
      if (c.tipo !== tipo) return false;
      if (filtros.status !== "todos" && c.status !== filtros.status) return false;
      if (corte && new Date(c.vencimento).getTime() > corte) return false;
      if (
        q &&
        !c.descricao.toLowerCase().includes(q) &&
        !c.contraparte.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [data, filtros, tipo]);

  const totaisPorStatus = React.useMemo(() => {
    const seed = { pendente: 0, pago: 0, atrasado: 0 } as Record<
      StatusContaPagarReceber,
      number
    >;
    return (data ?? [])
      .filter((c) => c.tipo === tipo)
      .reduce((acc, c) => {
        acc[c.status] += c.valor;
        return acc;
      }, seed);
  }, [data, tipo]);

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
            Controles · {titulo}
          </motion.span>
          <motion.h1
            variants={itemV}
            className="font-serif text-[26px] md:text-3xl tracking-tight text-[var(--color-ink)] leading-tight"
          >
            {titulo}
          </motion.h1>
          <motion.p
            variants={itemV}
            className="text-sm text-[var(--color-ink-2)] max-w-2xl mt-1"
          >
            Cada conta cadastrada entra automaticamente no fluxo de caixa.
            Marcar como {palavraAcao === "pagar" ? "paga" : "recebida"} já
            atualiza a projeção.
          </motion.p>
        </div>
        <motion.div variants={itemV}>
          <Button
            onClick={() => {
              setEditando(null);
              setAbertoForm(true);
            }}
          >
            <Plus className="size-4" />{" "}
            {tipo === "pagar" ? "Nova conta a pagar" : "Novo recebível"}
          </Button>
        </motion.div>
      </motion.header>

      <ControlesSubnav />

      {/* ── stat cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard
          label="Pendentes"
          valor={<Moeda valor={totaisPorStatus.pendente} />}
          pill={{ tom: "warn", texto: "aguardando" }}
        />
        <StatCard
          label="Atrasadas"
          valor={<Moeda valor={totaisPorStatus.atrasado} />}
          pill={{
            tom: totaisPorStatus.atrasado > 0 ? "error" : "neutral",
            texto: totaisPorStatus.atrasado > 0 ? "atenção" : "sem atrasos",
          }}
        />
        <StatCard
          label={tipo === "pagar" ? "Pagas (total)" : "Recebidas (total)"}
          valor={<Moeda valor={totaisPorStatus.pago} />}
          pill={{ tom: "ok", texto: "concluído" }}
        />
      </div>

      {/* ── filtros ── */}
      <Framed marks={false} tone="rule" surface="card" className="flex flex-col md:flex-row md:items-center gap-3">
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
          <Input
            value={filtros.q}
            onChange={(e) => void setFiltros({ q: e.target.value })}
            placeholder="Buscar por descrição ou contato"
            className="pl-9"
          />
        </div>
        <Select
          value={filtros.status}
          onValueChange={(v) => void setFiltros({ status: v })}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os status</SelectItem>
            <SelectItem value="pendente">Pendentes</SelectItem>
            <SelectItem value="atrasado">Atrasados</SelectItem>
            <SelectItem value="pago">
              {tipo === "pagar" ? "Pagas" : "Recebidas"}
            </SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filtros.vencimento}
          onValueChange={(v) => void setFiltros({ vencimento: v })}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30d">Vencem em 30 dias</SelectItem>
            <SelectItem value="60d">Vencem em 60 dias</SelectItem>
            <SelectItem value="90d">Vencem em 90 dias</SelectItem>
            <SelectItem value="todos">Todas</SelectItem>
          </SelectContent>
        </Select>
      </Framed>

      {/* ── conteúdo ── */}
      {isLoading ? (
        <LoadingState titulo="Carregando..." />
      ) : isError ? (
        <ErrorState onTentarNovamente={() => void refetch()} />
      ) : lista.length === 0 ? (
        <EmptyState
          titulo={
            tipo === "pagar"
              ? "Nenhuma conta a pagar nesse filtro"
              : "Nenhuma conta a receber nesse filtro"
          }
          descricao="Cadastre uma nova ou ajuste os filtros."
          acao={
            <Button
              onClick={() => {
                setEditando(null);
                setAbertoForm(true);
              }}
            >
              <Plus className="size-4" /> Cadastrar
            </Button>
          }
        />
      ) : (
        <Framed marks tone="ink" surface="card" padded={false} className="overflow-hidden">
          <div className="px-5 pt-4 pb-2">
            <Fig n={1} titulo={titulo} size="sm" />
          </div>
          <Ruler />
          <ul
            className="divide-y"
            style={{ borderColor: "var(--color-rule)" }}
          >
            {lista.map((conta) => (
              <LinhaConta
                key={conta.id}
                conta={conta}
                onEditar={() => {
                  setEditando(conta);
                  setAbertoForm(true);
                }}
                onMarcarPaga={async () => {
                  await marcarPaga.mutateAsync({
                    id: conta.id,
                    pagoEm: new Date().toISOString().slice(0, 10),
                  });
                  toast.success(
                    tipo === "pagar"
                      ? `${conta.descricao} marcada como paga`
                      : `${conta.descricao} marcada como recebida`
                  );
                }}
                onRemover={() => setConfirmandoRemocao(conta)}
              />
            ))}
          </ul>
          <Ruler />
          <div className="px-5 py-2.5">
            <span
              className="text-xs text-[var(--color-ink-3)] mono"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {lista.length} {tipo === "pagar" ? "conta(s) a pagar" : "conta(s) a receber"}
            </span>
          </div>
        </Framed>
      )}

      <ContaFormDialog
        tipo={tipo}
        aberto={abertoForm}
        conta={editando}
        salvando={adicionar.isPending || atualizar.isPending}
        onAbertoChange={(v) => {
          setAbertoForm(v);
          if (!v) setEditando(null);
        }}
        onSalvar={async (conta) => {
          if (editando) {
            await atualizar.mutateAsync(conta);
            toast.success("Conta atualizada");
          } else {
            await adicionar.mutateAsync(conta);
            toast.success(
              tipo === "pagar" ? "Conta a pagar criada" : "Conta a receber criada"
            );
          }
          setAbertoForm(false);
          setEditando(null);
        }}
      />

      <Dialog
        open={!!confirmandoRemocao}
        onOpenChange={(v) => {
          if (!v) setConfirmandoRemocao(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Excluir conta?</DialogTitle>
            <DialogDescription>
              {confirmandoRemocao
                ? `"${confirmandoRemocao.descricao}" será removida do fluxo de caixa.`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setConfirmandoRemocao(null)}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={remover.isPending}
              onClick={async () => {
                if (!confirmandoRemocao) return;
                await remover.mutateAsync(confirmandoRemocao.id);
                toast.success("Conta excluída");
                setConfirmandoRemocao(null);
              }}
            >
              Excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}

function LinhaConta({
  conta,
  onEditar,
  onMarcarPaga,
  onRemover,
}: {
  conta: ContaPagarReceber;
  onEditar: () => void;
  onMarcarPaga: () => Promise<void> | void;
  onRemover: () => void;
}) {
  return (
    <li className="px-5 py-3 flex flex-col md:flex-row md:items-center gap-3 hover:bg-[var(--color-paper-2)] transition-colors">
      <div className="flex flex-col shrink-0 w-28 gap-1">
        <span
          className="mono text-xs font-bold text-[var(--color-ink-2)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarDataBR(conta.vencimento)}
        </span>
        <StatusContaPill status={conta.status} />
      </div>
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-sm text-[var(--color-ink)] truncate">
          {conta.descricao}
        </span>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-ink-2)] flex-wrap">
          <span className="truncate">{conta.contraparte}</span>
          <span className="size-1 rounded-full bg-[var(--color-rule-2)]" />
          <span>{CATEGORIA_CONTA_LABEL[conta.categoria]}</span>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span
          className="mono text-base font-bold text-[var(--color-ink)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <Moeda valor={conta.valor} />
        </span>
        {conta.status !== "pago" ? (
          <Button
            variant="outline"
            onClick={() => void onMarcarPaga()}
            aria-label={
              conta.tipo === "pagar"
                ? "Marcar como paga"
                : "Marcar como recebida"
            }
          >
            <Check className="size-4" />{" "}
            {conta.tipo === "pagar" ? "Marcar paga" : "Recebida"}
          </Button>
        ) : null}
        <Button
          variant="ghost"
          onClick={onEditar}
          aria-label="Editar"
          className="px-2"
        >
          <Pencil className="size-4" />
        </Button>
        <Button
          variant="ghost"
          onClick={onRemover}
          aria-label="Excluir"
          className="px-2 text-[var(--color-danger)] hover:text-[var(--color-danger)]"
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
    </li>
  );
}

function corteDataDias(periodo: string): number | null {
  const dias =
    periodo === "30d"
      ? 30
      : periodo === "60d"
        ? 60
        : periodo === "90d"
          ? 90
          : null;
  if (dias == null) return null;
  return Date.now() + dias * 24 * 60 * 60 * 1000;
}
