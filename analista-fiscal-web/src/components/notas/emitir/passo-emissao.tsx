"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  FileText,
  Loader2,
  Send,
} from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
import { Framed } from "@/components/blueprint/framed";
import { Fig } from "@/components/blueprint/fig";
import { Ruler } from "@/components/blueprint/ruler";
import { BlueprintSchematic } from "@/components/blueprint/blueprint-schematic";
import { Carimbo } from "@/components/blueprint/carimbo";
import { useNfWizardStore } from "@/lib/stores/nf-wizard-store";
import { useEmpresaAtual } from "@/components/layout/empresa-provider";
import { useSalvarNota } from "@/hooks/use-notas";
import { totalizarNota } from "@/lib/notas/impostos";
import { montarChaveNFe, formatarChave } from "@/lib/notas/chave";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import { formatarDataBR } from "@/lib/format/data";
import { baixarDANFE, baixarXml } from "@/lib/notas/downloads";
import {
  reveal,
  revealChild,
  staggerChildren,
  staticVariants,
  EASE,
  DUR,
} from "@/lib/motion/variants";
import { useReducedMotion } from "@/lib/motion/use-reduced-motion";
import type { NotaFiscal } from "@/lib/schemas/nota";

type Estado = "conferencia" | "enviando" | "autorizada";

export function PassoEmissao() {
  const router = useRouter();
  const { empresa } = useEmpresaAtual();
  const wizard = useNfWizardStore();
  const salvar = useSalvarNota();
  const reduced = useReducedMotion();
  const [estado, setEstado] = React.useState<Estado>("conferencia");
  const [emitida, setEmitida] = React.useState<NotaFiscal | null>(null);

  const totais = React.useMemo(
    () => totalizarNota(wizard.itens),
    [wizard.itens]
  );

  if (!empresa || !wizard.contraparte) {
    return (
      <Framed marks={false} tone="rule" surface="card">
        <p className="text-sm text-[var(--color-ink-2)]">
          Volte ao passo 1 — destinatário ainda não definido.
        </p>
      </Framed>
    );
  }

  const cp = wizard.contraparte;

  const emitir = async () => {
    setEstado("enviando");
    await new Promise((r) => setTimeout(r, 2_400));

    const agora = new Date();
    const numero = String(Math.floor(Math.random() * 999_999) + 1).padStart(
      9,
      "0"
    );
    const chave = montarChaveNFe({
      uf: empresa.uf,
      ano: agora.getFullYear(),
      mes: agora.getMonth() + 1,
      cnpj: empresa.cnpj,
      numero: Number(numero),
    });

    const nota: NotaFiscal = {
      id: chave,
      chave,
      numero,
      serie: "001",
      tipo: "saida",
      status: "autorizada",
      emitidaEm: agora.toISOString(),
      cnpjEmitente: empresa.cnpj,
      razaoEmitente: empresa.razaoSocial,
      contraparte: cp,
      itens: wizard.itens,
      totais,
      pagamento: wizard.pagamento,
      observacao: wizard.observacao || undefined,
      protocoloAutorizacao: `135${String(agora.getFullYear()).slice(-2)}${String(agora.getMonth() + 1).padStart(2, "0")}${numero}`,
      cartasCorrecao: [],
    };

    await salvar.mutateAsync(nota);
    setEmitida(nota);
    setEstado("autorizada");
  };

  /* ── estado: enviando ── */
  if (estado === "enviando") {
    return (
      <Framed marks tone="rule" surface="paper-2" className="flex flex-col items-center justify-center gap-5 text-center py-10">
        <BlueprintSchematic width={120} figure="nota" />
        <div className="flex flex-col items-center gap-2">
          <Loader2
            className="size-6 animate-spin"
            style={{ color: "var(--color-green)" }}
          />
          <h2 className="font-serif text-lg text-[var(--color-ink)]">
            Comunicando com a SEFAZ...
          </h2>
          <p className="text-sm text-[var(--color-ink-2)] max-w-md">
            Enviando a nota, aguardando autorização e protocolo. Não feche essa aba.
          </p>
        </div>
        <ul
          className="text-[12px] text-[var(--color-ink-3)] mono space-y-1 mt-1 text-left"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          <li>· Validando schema XSD</li>
          <li>· Assinando com certificado A1</li>
          <li>· Aguardando autorização da SEFAZ</li>
        </ul>
      </Framed>
    );
  }

  /* ── estado: autorizada ── */
  if (estado === "autorizada" && emitida) {
    return (
      <EmissaoSucesso
        nota={emitida}
        onAbrirDetalhe={() => router.push(`/notas/${emitida.chave}`)}
        reduced={reduced}
      />
    );
  }

  /* ── estado: conferência ── */
  const containerVariants = reduced ? staticVariants : staggerChildren;
  const itemVariants = reduced ? staticVariants : revealChild;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-4">
      <Framed marks tone="ink" surface="card" className="flex flex-col gap-4">
        <Fig n={4} titulo="Conferência antes de emitir" />
        <Ruler />

        <motion.div
          className="flex flex-col gap-3 pt-1"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {/* destinatário */}
          <motion.div
            variants={itemVariants}
            className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-2"
            style={{
              background: "var(--color-paper-2)",
              borderColor: "var(--color-rule-2)",
            }}
          >
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
              Destinatário
            </span>
            <div className="flex flex-col">
              <span className="font-serif text-base text-[var(--color-ink)]">
                {cp.nome}
              </span>
              <span
                className="mono text-xs text-[var(--color-ink-2)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {cp.tipo === "pj"
                  ? formatarCNPJ(cp.documento)
                  : formatarCPF(cp.documento)}
              </span>
            </div>
            {cp.endereco ? (
              <span className="text-[12px] text-[var(--color-ink-3)] leading-snug">
                {cp.endereco.logradouro}, {cp.endereco.numero} ·{" "}
                {cp.endereco.municipio}/{cp.endereco.uf}
              </span>
            ) : null}
          </motion.div>

          {/* itens */}
          <motion.div
            variants={itemVariants}
            className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-2"
            style={{
              background: "var(--color-paper-2)",
              borderColor: "var(--color-rule-2)",
            }}
          >
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
              Itens ({wizard.itens.length})
            </span>
            <ul className="flex flex-col gap-1.5">
              {wizard.itens.map((it) => (
                <li
                  key={it.id}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="text-[var(--color-ink)] truncate">
                    {it.descricao}
                  </span>
                  <span
                    className="mono text-[var(--color-ink-2)] shrink-0"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {it.quantidade.toString().replace(".", ",")} ×{" "}
                    {formatarMoeda(it.valorUnitario)}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>

          {/* pagamento */}
          <motion.div
            variants={itemVariants}
            className="rounded-[var(--radius-md)] border p-4 flex flex-col gap-1"
            style={{
              background: "var(--color-paper-2)",
              borderColor: "var(--color-rule-2)",
            }}
          >
            <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
              Pagamento
            </span>
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--color-ink-2)]">
                {labelForma(wizard.pagamento.forma)}
                {wizard.pagamento.parcelas > 1
                  ? ` em ${wizard.pagamento.parcelas}x`
                  : ""}
              </span>
              <span
                className="mono text-[var(--color-ink)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                vence {formatarDataBR(wizard.pagamento.vencimento)}
              </span>
            </div>
          </motion.div>
        </motion.div>

        <Ruler />
        <div className="flex justify-between items-center">
          <Button variant="ghost" onClick={wizard.voltar}>
            <ArrowLeft className="size-3.5" /> Voltar
          </Button>
        </div>
      </Framed>

      {/* ── painel de emissão ── */}
      <Framed marks={false} tone="rule" surface="paper-2" className="flex flex-col gap-4 self-start lg:sticky lg:top-4">
        <Fig n={5} titulo="Resumo legível" />
        <Ruler />
        <p className="text-[15px] text-[var(--color-ink)] leading-relaxed pt-1">
          Você está vendendo{" "}
          <strong
            className="mono"
            style={{ color: "var(--color-green)", fontVariantNumeric: "tabular-nums" }}
          >
            {formatarMoeda(totais.valorNota)}
          </strong>{" "}
          em{" "}
          {wizard.itens.some((i) => i.aliquotaIcms) ? "produtos" : "serviços"}{" "}
          para{" "}
          <strong className="text-[var(--color-ink)]">{cp.nome}</strong>.
          {totais.totalImpostos > 0 ? (
            <>
              {" "}
              Imposto incluso (estimado):{" "}
              <span
                className="mono text-[var(--color-ink-2)]"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatarMoeda(totais.totalImpostos)}
              </span>
              .
            </>
          ) : null}
        </p>

        <Button onClick={emitir} size="lg" className="w-full h-12 text-base">
          <Send className="size-4" />
          Emitir nota fiscal
        </Button>

        <p className="text-[11px] text-[var(--color-ink-3)] leading-snug text-center">
          A nota é enviada à SEFAZ assinada digitalmente. Você recebe o
          protocolo em alguns segundos.
        </p>
      </Framed>
    </div>
  );
}

/* ── sucesso de emissão ── */
function EmissaoSucesso({
  nota,
  onAbrirDetalhe,
  reduced,
}: {
  nota: NotaFiscal;
  onAbrirDetalhe: () => void;
  reduced: boolean;
}) {
  return (
    <Framed marks tone="ink" surface="card" className="flex flex-col items-center text-center gap-5 max-w-2xl mx-auto py-10">
      {/* BlueprintSchematic como elemento de assinatura — a nota desenhada */}
      <BlueprintSchematic width={140} figure="nota" />

      {/* Carimbo "Autorizada" — signature motion */}
      <Carimbo tom="green" sub={formatarDataBR(nota.emitidaEm)}>
        Autorizada
      </Carimbo>

      <div className="flex flex-col gap-1">
        <Pill tom="ok" semIcone>Protocolo recebido</Pill>
        <h2 className="font-serif text-2xl text-[var(--color-ink)] tracking-tight mt-2">
          Nota fiscal emitida
        </h2>
        <p className="text-sm text-[var(--color-ink-2)] max-w-md leading-relaxed">
          A SEFAZ autorizou a NF-e nº{" "}
          <span
            className="mono text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {nota.numero}
          </span>{" "}
          sob o protocolo{" "}
          <span
            className="mono text-[var(--color-ink)]"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {nota.protocoloAutorizacao}
          </span>
          .
        </p>
      </div>

      {/* chave de acesso */}
      <div
        className="rounded-[var(--radius-md)] border p-3 w-full max-w-md flex flex-col gap-1.5 text-left"
        style={{
          background: "var(--color-paper-2)",
          borderColor: "var(--color-rule-2)",
        }}
      >
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-ink-3)] mono">
          Chave de acesso
        </span>
        <span
          className="mono text-[12px] text-[var(--color-ink)] break-all leading-relaxed"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatarChave(nota.chave)}
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button onClick={() => baixarDANFE(nota)} variant="outline" size="sm">
          <FileText className="size-3.5" /> Baixar DANFE (PDF)
        </Button>
        <Button onClick={() => baixarXml(nota)} variant="outline" size="sm">
          <Download className="size-3.5" /> Baixar XML
        </Button>
        <Button onClick={onAbrirDetalhe} size="sm">
          Ver nota emitida
        </Button>
      </div>

      <Link
        href="/notas/saida/nova"
        onClick={(e) => {
          e.preventDefault();
          useNfWizardStore.getState().resetar();
        }}
        className="text-xs text-[var(--color-ink-3)] hover:text-[var(--color-ink)] transition-colors"
      >
        Emitir outra nota
      </Link>

      {/* preservado por invariante — componente funcional */}
      <Moeda valor={nota.totais.valorNota} className="hidden" />
    </Framed>
  );
}

function labelForma(
  f: NotaFiscal["pagamento"] extends infer P
    ? P extends { forma: infer F }
      ? F
      : never
    : never
): string {
  const map: Record<string, string> = {
    pix: "PIX",
    boleto: "Boleto",
    transferencia: "Transferência",
    cartao_credito: "Cartão de crédito",
    cartao_debito: "Cartão de débito",
    dinheiro: "Dinheiro",
    outros: "Outros",
  };
  return map[f as string] ?? "—";
}
