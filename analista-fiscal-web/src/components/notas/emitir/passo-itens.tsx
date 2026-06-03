"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, Plus, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useProdutosCatalogo } from "@/hooks/use-notas";
import { calcularImpostosItem, totalizarNota } from "@/lib/notas/impostos";
import { formatarMoeda } from "@/lib/format/moeda";
import type { ProdutoCatalogo } from "@/lib/schemas/nota";

export function PassoItens() {
  const { empresa } = useEmpresaAtual();
  const {
    contraparte,
    itens,
    adicionarItem,
    removerItem,
    proximo,
    voltar,
  } = useNfWizardStore();
  const { data: catalogo } = useProdutosCatalogo();

  const [busca, setBusca] = React.useState("");
  const [aberto, setAberto] = React.useState(false);
  const [produto, setProduto] = React.useState<ProdutoCatalogo | null>(null);
  const [qtd, setQtd] = React.useState("1");
  const [preco, setPreco] = React.useState("");

  const sugestoes = React.useMemo(() => {
    if (!catalogo || !busca.trim()) return catalogo ?? [];
    const q = busca.trim().toLowerCase();
    return catalogo.filter((p) => p.descricao.toLowerCase().includes(q));
  }, [catalogo, busca]);

  const totais = React.useMemo(() => totalizarNota(itens), [itens]);

  const adicionar = () => {
    if (!empresa || !contraparte || !produto) return;
    const item = calcularImpostosItem({
      empresa,
      contraparte,
      entrada: {
        produto,
        descricao: produto.descricao,
        unidade: produto.unidade,
        quantidade: Number(qtd) || 1,
        valorUnitario: Number(preco) || produto.precoSugerido,
      },
    });
    adicionarItem(item);
    setProduto(null);
    setBusca("");
    setQtd("1");
    setPreco("");
    setAberto(false);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
      {/* ── painel principal ── */}
      <Framed marks tone="ink" surface="card" className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <Fig n={2} titulo="O que você está vendendo?" />
          {itens.length > 0 ? (
            <span
              className="mono text-xs text-[var(--color-ink-3)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {itens.length} item(ns)
            </span>
          ) : null}
        </div>
        <Ruler />

        {/* busca no catálogo */}
        <div className="flex flex-col gap-2 pt-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-ink-3)]" />
            <Input
              value={busca}
              onChange={(e) => {
                setBusca(e.target.value);
                setAberto(true);
              }}
              onFocus={() => setAberto(true)}
              placeholder="Buscar no catálogo (ex: consultoria, hora técnica, notebook)"
              className="pl-9"
            />
          </div>
          {aberto && sugestoes.length > 0 ? (
            <Framed marks={false} tone="rule" surface="card" padded={false} className="max-h-[260px] overflow-auto">
              <ul className="flex flex-col p-1">
                {sugestoes.slice(0, 8).map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setProduto(p);
                        setPreco(String(p.precoSugerido));
                        setAberto(false);
                      }}
                      className="w-full text-left flex items-center justify-between gap-3 px-3 py-2 rounded-[var(--radius-sm)] hover:bg-[var(--color-paper-2)] transition-colors"
                    >
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-[var(--color-ink)] truncate">
                          {p.descricao}
                        </span>
                        <span className="text-[11px] text-[var(--color-ink-3)] mono">
                          {p.tipo === "servico" ? "serviço" : "produto"} · un. {p.unidade}
                        </span>
                      </div>
                      <span
                        className="mono text-xs text-[var(--color-ink-2)] shrink-0"
                        style={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {formatarMoeda(p.precoSugerido)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Framed>
          ) : null}
        </div>

        {/* produto selecionado */}
        {produto ? (
          <div
            className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-3"
            style={{
              background: "var(--color-green-wash)",
              borderColor: "var(--color-green)",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-[var(--color-ink)]">
                {produto.descricao}
              </span>
              <Pill tom={produto.tipo === "servico" ? "info" : "ok"}>
                {produto.tipo === "servico" ? "serviço" : produto.tipo}
              </Pill>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>Quantidade</Label>
                <Input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={qtd}
                  onChange={(e) => setQtd(e.target.value)}
                  className="mono"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Valor unitário (R$)</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={preco}
                  onChange={(e) => setPreco(e.target.value)}
                  className="mono"
                />
              </div>
            </div>
            <Button onClick={adicionar} size="sm" className="self-start">
              <Plus className="size-3.5" /> Adicionar à nota
            </Button>
          </div>
        ) : null}

        {/* lista de itens */}
        {itens.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {itens.map((it) => (
              <li
                key={it.id}
                className="rounded-[var(--radius-md)] border p-3 flex items-center gap-3"
                style={{
                  background: "var(--color-paper-2)",
                  borderColor: "var(--color-rule-2)",
                }}
              >
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-sm text-[var(--color-ink)] truncate">
                    {it.descricao}
                  </span>
                  <span
                    className="text-[11px] text-[var(--color-ink-3)] mono"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {it.quantidade.toString().replace(".", ",")} {it.unidade} ·{" "}
                    {formatarMoeda(it.valorUnitario)} cada
                  </span>
                </div>
                <span
                  className="mono text-sm font-bold text-[var(--color-ink)] shrink-0"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {formatarMoeda(it.valorTotal)}
                </span>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-8 text-[var(--color-danger)]"
                  onClick={() => removerItem(it.id)}
                  aria-label={`Remover ${it.descricao}`}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-[var(--color-ink-3)] italic text-center py-6">
            Adicione ao menos um item para continuar.
          </p>
        )}

        <Ruler />
        <div className="flex justify-between items-center">
          <Button variant="ghost" onClick={voltar}>
            <ArrowLeft className="size-3.5" /> Voltar
          </Button>
          <Button onClick={proximo} disabled={itens.length === 0} size="lg">
            Continuar <ArrowRight className="size-4" />
          </Button>
        </div>
      </Framed>

      {/* ── resumo lateral ── */}
      <Framed marks={false} tone="rule" surface="paper-2" className="flex flex-col gap-3 self-start sticky top-4">
        <Fig n={3} titulo="Resumo da nota" />
        <Ruler />
        <div className="flex flex-col gap-1.5 text-sm pt-1">
          <Linha label="Produtos / Serviços" valor={totais.produtos} />
          {totais.icms > 0 ? (
            <Linha label="ICMS embutido" valor={totais.icms} sub />
          ) : null}
          {totais.iss > 0 ? (
            <Linha label="ISS embutido" valor={totais.iss} sub />
          ) : null}
          {totais.pis > 0 ? (
            <Linha label="PIS embutido" valor={totais.pis} sub />
          ) : null}
          {totais.cofins > 0 ? (
            <Linha label="Cofins embutido" valor={totais.cofins} sub />
          ) : null}
        </div>

        <div
          className="border-t pt-3"
          style={{ borderColor: "var(--color-rule)" }}
        >
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-[0.18em] font-bold text-[var(--color-ink-3)] mono">
              Total da nota
            </span>
            <span
              className="mono text-2xl font-extrabold text-[var(--color-ink)]"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              <Moeda valor={totais.valorNota} />
            </span>
          </div>
          {totais.totalImpostos > 0 ? (
            <p className="text-[11px] text-[var(--color-ink-3)] mt-1.5 leading-snug">
              Imposto incluso (estimado):{" "}
              <span
                className="mono text-[var(--color-ink-2)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarMoeda(totais.totalImpostos)}
              </span>
              .
            </p>
          ) : null}
        </div>

        <p className="text-[11px] text-[var(--color-ink-3)] leading-snug">
          CFOP, NCM, CST e alíquotas são calculados automaticamente — com base
          em{" "}
          {empresa?.regime?.replace("_", " ").toLowerCase() ?? "regime"} e UF
          de destino.
        </p>
      </Framed>
    </div>
  );
}

function Linha({
  label,
  valor,
  sub,
}: {
  label: string;
  valor: number;
  sub?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span
        className={
          sub
            ? "text-[11px] text-[var(--color-ink-3)]"
            : "text-[var(--color-ink-2)]"
        }
      >
        {label}
      </span>
      <span
        className={
          sub
            ? "mono text-[11px] text-[var(--color-ink-3)]"
            : "mono text-[var(--color-ink)]"
        }
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}
