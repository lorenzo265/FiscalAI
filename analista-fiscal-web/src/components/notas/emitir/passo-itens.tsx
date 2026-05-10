"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, Plus, Search, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
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
      <Card className="p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
            O que você está vendendo?
          </span>
          {itens.length > 0 ? (
            <span className="mono text-xs text-[var(--color-txt-3)]">
              {itens.length} item(ns)
            </span>
          ) : null}
        </div>

        <div className="flex flex-col gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-[var(--color-txt-3)]" />
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
            <Card className="max-h-[260px] overflow-auto p-1">
              <ul className="flex flex-col">
                {sugestoes.slice(0, 8).map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setProduto(p);
                        setPreco(String(p.precoSugerido));
                        setAberto(false);
                      }}
                      className="w-full text-left flex items-center justify-between gap-3 px-3 py-2 rounded-sm hover:bg-[var(--color-card-2)] transition-colors"
                    >
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-[var(--color-txt)] truncate">
                          {p.descricao}
                        </span>
                        <span className="text-[11px] text-[var(--color-txt-3)] mono">
                          {p.tipo === "servico" ? "serviço" : "produto"} · un. {p.unidade}
                        </span>
                      </div>
                      <span className="mono text-xs text-[var(--color-txt-2)] shrink-0">
                        {formatarMoeda(p.precoSugerido)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>

        {produto ? (
          <div
            className="rounded-md border p-4 flex flex-col gap-3"
            style={{
              background: "var(--color-card-2)",
              borderColor: "rgba(163,255,107,0.18)",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-[var(--color-txt)]">
                {produto.descricao}
              </span>
              <Pill tom={produto.tipo === "servico" ? "info" : "ok"}>
                {produto.tipo}
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

        {itens.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {itens.map((it) => (
              <li
                key={it.id}
                className="rounded-md border p-3 flex items-center gap-3"
                style={{
                  background: "var(--color-card-2)",
                  borderColor: "var(--color-line-2)",
                }}
              >
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-sm text-[var(--color-txt)] truncate">
                    {it.descricao}
                  </span>
                  <span className="text-[11px] text-[var(--color-txt-3)] mono">
                    {it.quantidade.toString().replace(".", ",")} {it.unidade} ·{" "}
                    {formatarMoeda(it.valorUnitario)} cada
                  </span>
                </div>
                <span className="mono text-sm font-bold text-[var(--color-txt)] shrink-0">
                  {formatarMoeda(it.valorTotal)}
                </span>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-8 text-[var(--color-red)]"
                  onClick={() => removerItem(it.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-[var(--color-txt-3)] italic text-center py-6">
            Adicione ao menos um item pra continuar.
          </p>
        )}

        <div className="flex justify-between items-center pt-2 border-t" style={{ borderColor: "var(--color-line)" }}>
          <Button variant="ghost" onClick={voltar}>
            <ArrowLeft className="size-3.5" /> Voltar
          </Button>
          <Button
            onClick={proximo}
            disabled={itens.length === 0}
            size="lg"
          >
            Continuar <ArrowRight className="size-4" />
          </Button>
        </div>
      </Card>

      <Card className="p-5 flex flex-col gap-3 self-start sticky top-4">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Resumo da nota
        </span>

        <div className="flex flex-col gap-1 text-sm">
          <Linha label="Produtos / Serviços" valor={totais.produtos} />
          {totais.icms > 0 ? <Linha label="ICMS embutido" valor={totais.icms} sub /> : null}
          {totais.iss > 0 ? <Linha label="ISS embutido" valor={totais.iss} sub /> : null}
          {totais.pis > 0 ? <Linha label="PIS embutido" valor={totais.pis} sub /> : null}
          {totais.cofins > 0 ? <Linha label="Cofins embutido" valor={totais.cofins} sub /> : null}
        </div>

        <div className="border-t pt-3" style={{ borderColor: "var(--color-line)" }}>
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
              Total da nota
            </span>
            <span className="mono text-2xl font-extrabold text-[var(--color-txt)]">
              <Moeda valor={totais.valorNota} />
            </span>
          </div>
          {totais.totalImpostos > 0 ? (
            <p className="text-[11px] text-[var(--color-txt-3)] mt-1.5 leading-snug">
              Imposto incluso (estimado):{" "}
              <span className="mono text-[var(--color-txt-2)]">
                {formatarMoeda(totais.totalImpostos)}
              </span>
              .
            </p>
          ) : null}
        </div>

        <p className="text-[11px] text-[var(--color-txt-3)] leading-snug">
          CFOP, NCM, CST e alíquotas são calculados automaticamente —
          baseando-se em {empresa?.regime?.replace("_", " ").toLowerCase()} e
          UF de destino.
        </p>
      </Card>
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
            ? "text-[11px] text-[var(--color-txt-3)]"
            : "text-[var(--color-txt-2)]"
        }
      >
        {label}
      </span>
      <span
        className={
          sub
            ? "mono text-[11px] text-[var(--color-txt-3)]"
            : "mono text-[var(--color-txt)]"
        }
      >
        {formatarMoeda(valor)}
      </span>
    </div>
  );
}
