"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Send,
} from "lucide-react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/shared/pill";
import { Moeda } from "@/components/shared/moeda";
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
import type { NotaFiscal } from "@/lib/schemas/nota";

type Estado = "conferencia" | "enviando" | "autorizada";

export function PassoEmissao() {
  const router = useRouter();
  const { empresa } = useEmpresaAtual();
  const wizard = useNfWizardStore();
  const salvar = useSalvarNota();
  const [estado, setEstado] = React.useState<Estado>("conferencia");
  const [emitida, setEmitida] = React.useState<NotaFiscal | null>(null);

  const totais = React.useMemo(
    () => totalizarNota(wizard.itens),
    [wizard.itens]
  );

  if (!empresa || !wizard.contraparte) {
    return (
      <Card className="p-6">
        <p className="text-sm text-[var(--color-txt-2)]">
          Volte ao passo 1 — destinatário ainda não definido.
        </p>
      </Card>
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

  if (estado === "enviando") {
    return (
      <Card className="p-10 flex flex-col items-center justify-center gap-4 text-center">
        <Loader2 className="size-10 animate-spin text-[var(--color-lime)]" />
        <h2 className="text-lg font-semibold text-[var(--color-txt)]">
          Comunicando com a SEFAZ...
        </h2>
        <p className="text-sm text-[var(--color-txt-2)] max-w-md">
          Enviando a nota, aguardando autorização e protocolo. Não feche essa
          aba.
        </p>
        <ul className="text-[12px] text-[var(--color-txt-3)] mono space-y-1 mt-2">
          <li>· Validando schema XSD</li>
          <li>· Assinando com certificado A1</li>
          <li>· Aguardando autorização da SEFAZ</li>
        </ul>
      </Card>
    );
  }

  if (estado === "autorizada" && emitida) {
    return <EmissaoSucesso nota={emitida} onAbrirDetalhe={() => router.push(`/notas/${emitida.chave}`)} />;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-4">
      <Card className="p-5 flex flex-col gap-4">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Confira antes de emitir
        </span>

        <div className="rounded-md border p-4 flex flex-col gap-3" style={{ background: "var(--color-card-2)", borderColor: "var(--color-line-2)" }}>
          <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
            Destinatário
          </span>
          <div className="flex flex-col">
            <span className="text-base font-semibold text-[var(--color-txt)]">
              {cp.nome}
            </span>
            <span className="mono text-xs text-[var(--color-txt-2)]">
              {cp.tipo === "pj"
                ? formatarCNPJ(cp.documento)
                : formatarCPF(cp.documento)}
            </span>
          </div>
          {cp.endereco ? (
            <span className="text-[12px] text-[var(--color-txt-3)] leading-snug">
              {cp.endereco.logradouro}, {cp.endereco.numero} ·{" "}
              {cp.endereco.municipio}/{cp.endereco.uf}
            </span>
          ) : null}
        </div>

        <div className="rounded-md border p-4 flex flex-col gap-2" style={{ background: "var(--color-card-2)", borderColor: "var(--color-line-2)" }}>
          <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
            Itens ({wizard.itens.length})
          </span>
          <ul className="flex flex-col gap-1.5">
            {wizard.itens.map((it) => (
              <li
                key={it.id}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="text-[var(--color-txt)] truncate">
                  {it.descricao}
                </span>
                <span className="mono text-[var(--color-txt-2)] shrink-0">
                  {it.quantidade.toString().replace(".", ",")} ×{" "}
                  {formatarMoeda(it.valorUnitario)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-md border p-4 flex flex-col gap-2" style={{ background: "var(--color-card-2)", borderColor: "var(--color-line-2)" }}>
          <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
            Pagamento
          </span>
          <div className="flex items-center justify-between text-sm">
            <span className="text-[var(--color-txt-2)]">
              {labelForma(wizard.pagamento.forma)}
              {wizard.pagamento.parcelas > 1
                ? ` em ${wizard.pagamento.parcelas}x`
                : ""}
            </span>
            <span className="mono text-[var(--color-txt)]">
              vence {formatarDataBR(wizard.pagamento.vencimento)}
            </span>
          </div>
        </div>

        <div
          className="flex justify-between items-center pt-2 border-t"
          style={{ borderColor: "var(--color-line)" }}
        >
          <Button variant="ghost" onClick={wizard.voltar}>
            <ArrowLeft className="size-3.5" /> Voltar
          </Button>
        </div>
      </Card>

      <Card className="p-5 flex flex-col gap-4 self-start lg:sticky lg:top-4">
        <span className="text-[10px] uppercase tracking-[0.16em] font-bold text-[var(--color-txt-3)] mono">
          Resumo legível
        </span>
        <p className="text-[15px] text-[var(--color-txt)] leading-relaxed">
          Você está vendendo{" "}
          <strong className="text-[var(--color-lime)] mono">
            {formatarMoeda(totais.valorNota)}
          </strong>{" "}
          em {wizard.itens.some((i) => i.aliquotaIcms) ? "produtos" : "serviços"}{" "}
          para <strong className="text-[var(--color-txt)]">{cp.nome}</strong>.
          {totais.totalImpostos > 0 ? (
            <>
              {" "}
              Imposto incluso (estimado):{" "}
              <span className="mono text-[var(--color-txt-2)]">
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

        <p className="text-[11px] text-[var(--color-txt-3)] leading-snug text-center">
          A nota é enviada pra SEFAZ assinada digitalmente. Você recebe o
          protocolo em alguns segundos.
        </p>
      </Card>
    </div>
  );
}

function EmissaoSucesso({
  nota,
  onAbrirDetalhe,
}: {
  nota: NotaFiscal;
  onAbrirDetalhe: () => void;
}) {
  return (
    <Card className="p-8 md:p-10 flex flex-col items-center text-center gap-4 max-w-2xl mx-auto">
      <motion.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", duration: 0.5 }}
        className="size-16 rounded-full grid place-items-center"
        style={{ background: "var(--color-lime-d)" }}
      >
        <CheckCircle2 className="size-8 text-[var(--color-lime)]" />
      </motion.div>

      <Pill tom="ok">Autorizada</Pill>
      <h2 className="text-2xl font-extrabold text-[var(--color-txt)] tracking-tight">
        Nota fiscal emitida com sucesso
      </h2>
      <p className="text-sm text-[var(--color-txt-2)] max-w-md leading-relaxed">
        A SEFAZ autorizou a NF-e nº{" "}
        <span className="mono text-[var(--color-txt)]">{nota.numero}</span> sob
        o protocolo{" "}
        <span className="mono text-[var(--color-txt)]">
          {nota.protocoloAutorizacao}
        </span>
        .
      </p>

      <div
        className="rounded-md border p-3 w-full max-w-md flex flex-col gap-1.5 text-left"
        style={{
          background: "var(--color-card-2)",
          borderColor: "var(--color-line-2)",
        }}
      >
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[var(--color-txt-3)] mono">
          Chave de acesso
        </span>
        <span className="mono text-[12px] text-[var(--color-txt)] break-all leading-relaxed">
          {formatarChave(nota.chave)}
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
        <Button onClick={() => baixarDANFE(nota)} variant="outline">
          <FileText className="size-3.5" /> Baixar DANFE (PDF)
        </Button>
        <Button onClick={() => baixarXml(nota)} variant="outline">
          <Download className="size-3.5" /> Baixar XML
        </Button>
        <Button onClick={onAbrirDetalhe}>Ver nota emitida</Button>
      </div>

      <Link
        href="/notas/saida/nova"
        onClick={(e) => {
          e.preventDefault();
          useNfWizardStore.getState().resetar();
        }}
        className="text-xs text-[var(--color-txt-3)] hover:text-[var(--color-txt)] transition-colors mt-2"
      >
        Emitir outra nota
      </Link>

      <Moeda valor={nota.totais.valorNota} className="hidden" />
    </Card>
  );
}

function labelForma(f: NotaFiscal["pagamento"] extends infer P ? P extends { forma: infer F } ? F : never : never): string {
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
