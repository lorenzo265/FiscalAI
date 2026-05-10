import { jsPDF } from "jspdf";
import JsBarcode from "jsbarcode";
import type { NotaFiscal } from "@/lib/schemas/nota";
import { formatarChave } from "@/lib/notas/chave";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataHoraBR } from "@/lib/format/data";

export function gerarPdfDANFE(nota: NotaFiscal): jsPDF {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 10;

  // === Cabeçalho preto com logo FiscalAI ===
  doc.setFillColor(6, 8, 15);
  doc.rect(0, 0, pageW, 26, "F");

  doc.setTextColor(163, 255, 107);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("FiscalAI", margin, 14);

  doc.setTextColor(221, 227, 240);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.text("DANFE — Documento Auxiliar da NF-e", margin, 19);

  doc.setFontSize(7);
  doc.setTextColor(136, 146, 168);
  doc.text(
    `${nota.tipo === "saida" ? "0 — Entrada · " : ""}1 — Saída · Modelo 55 · Série ${nota.serie} · Nº ${formatarNumeroNFe(nota.numero)}`,
    pageW - margin,
    14,
    { align: "right" }
  );
  doc.text(
    `Emitida em ${formatarDataHoraBR(nota.emitidaEm)}`,
    pageW - margin,
    19,
    { align: "right" }
  );

  // === Bloco chave ===
  let cursorY = 32;
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.3);
  doc.rect(margin, cursorY, pageW - margin * 2, 22);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text("CHAVE DE ACESSO", margin + 3, cursorY + 5);

  try {
    const canvas =
      typeof document !== "undefined" ? document.createElement("canvas") : null;
    if (canvas) {
      JsBarcode(canvas, nota.chave, {
        format: "CODE128",
        width: 1.2,
        height: 40,
        displayValue: false,
        margin: 0,
      });
      const img = canvas.toDataURL("image/png");
      doc.addImage(img, "PNG", margin + 3, cursorY + 7, 110, 12);
    }
  } catch (err) {
    console.warn("Falha barcode:", err);
  }

  doc.setFont("courier", "normal");
  doc.setFontSize(9);
  doc.setTextColor(20, 20, 20);
  doc.text(formatarChave(nota.chave), margin + 116, cursorY + 12);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text(
    `Protocolo de autorização: ${nota.protocoloAutorizacao ?? "—"}`,
    margin + 116,
    cursorY + 17
  );

  cursorY += 26;

  // === Emitente ===
  doc.rect(margin, cursorY, pageW - margin * 2, 18);
  campo(doc, margin + 3, cursorY + 5, "EMITENTE", nota.razaoEmitente, 11);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text(`CNPJ ${formatarCNPJ(nota.cnpjEmitente)}`, margin + 3, cursorY + 16);
  cursorY += 22;

  // === Destinatário ===
  doc.rect(margin, cursorY, pageW - margin * 2, 22);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text("DESTINATÁRIO / REMETENTE", margin + 3, cursorY + 5);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(20, 20, 20);
  doc.text(nota.contraparte.nome, margin + 3, cursorY + 11);

  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text(
    nota.contraparte.tipo === "pj"
      ? `CNPJ ${formatarCNPJ(nota.contraparte.documento)}`
      : `CPF ${formatarCPF(nota.contraparte.documento)}`,
    margin + 3,
    cursorY + 16
  );
  if (nota.contraparte.endereco) {
    const e = nota.contraparte.endereco;
    doc.text(
      `${e.logradouro}, ${e.numero}${e.complemento ? " · " + e.complemento : ""} · ${e.bairro} · ${e.municipio}/${e.uf} · CEP ${e.cep}`,
      margin + 3,
      cursorY + 20,
      { maxWidth: pageW - margin * 2 - 6 }
    );
  }
  cursorY += 26;

  // === Tabela itens ===
  doc.setFillColor(245, 245, 248);
  doc.rect(margin, cursorY, pageW - margin * 2, 6, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(80, 80, 80);
  const cols = [
    { label: "DESCRIÇÃO", x: margin + 3, w: 90, align: "left" as const },
    { label: "NCM", x: margin + 95, w: 18, align: "left" as const },
    { label: "CFOP", x: margin + 115, w: 12, align: "left" as const },
    { label: "QTD", x: margin + 132, w: 14, align: "right" as const },
    { label: "VL.UNIT.", x: margin + 152, w: 18, align: "right" as const },
    { label: "VL.TOTAL", x: margin + 173, w: 24, align: "right" as const },
  ];
  for (const c of cols) {
    doc.text(c.label, c.x + (c.align === "right" ? c.w : 0), cursorY + 4, {
      align: c.align,
    });
  }
  cursorY += 6;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(20, 20, 20);
  for (const item of nota.itens) {
    const desc = doc.splitTextToSize(item.descricao, 90);
    const linhaH = Math.max(5, desc.length * 4);
    if (cursorY + linhaH > pageH - 60) {
      doc.addPage();
      cursorY = margin;
    }
    doc.text(desc, margin + 3, cursorY + 4);
    doc.text(item.ncm, margin + 95, cursorY + 4);
    doc.text(item.cfop, margin + 115, cursorY + 4);
    doc.text(
      `${item.quantidade.toFixed(2)} ${item.unidade}`,
      margin + 146,
      cursorY + 4,
      { align: "right" }
    );
    doc.text(formatarMoeda(item.valorUnitario), margin + 170, cursorY + 4, {
      align: "right",
    });
    doc.text(formatarMoeda(item.valorTotal), margin + 197, cursorY + 4, {
      align: "right",
    });
    cursorY += linhaH;
    doc.setDrawColor(238, 238, 240);
    doc.line(margin, cursorY, pageW - margin, cursorY);
  }
  cursorY += 4;

  // === Totais ===
  doc.setDrawColor(220, 220, 220);
  doc.rect(margin, cursorY, pageW - margin * 2, 22);
  const tCol = (pageW - margin * 2) / 5;
  campoMini(doc, margin + 3, cursorY + 5, "BC ICMS", formatarMoeda(0));
  campoMini(
    doc,
    margin + 3 + tCol,
    cursorY + 5,
    "VL.ICMS",
    formatarMoeda(nota.totais.icms)
  );
  campoMini(
    doc,
    margin + 3 + tCol * 2,
    cursorY + 5,
    "VL.PIS",
    formatarMoeda(nota.totais.pis)
  );
  campoMini(
    doc,
    margin + 3 + tCol * 3,
    cursorY + 5,
    "VL.COFINS",
    formatarMoeda(nota.totais.cofins)
  );
  campoMini(
    doc,
    margin + 3 + tCol * 4,
    cursorY + 5,
    "VL.PRODUTOS",
    formatarMoeda(nota.totais.produtos)
  );

  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text(
    "VALOR TOTAL DA NOTA",
    pageW - margin - 3,
    cursorY + 14,
    { align: "right" }
  );
  doc.setFontSize(16);
  doc.setTextColor(0, 0, 0);
  doc.text(
    formatarMoeda(nota.totais.valorNota),
    pageW - margin - 3,
    cursorY + 21,
    { align: "right" }
  );
  cursorY += 26;

  // === Infos adicionais ===
  doc.rect(margin, cursorY, pageW - margin * 2, 22);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text("DADOS ADICIONAIS", margin + 3, cursorY + 5);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(60, 60, 60);
  const obs =
    nota.observacao ??
    "Documento mock gerado pelo FiscalAI · sem validade fiscal. Pagamento conforme combinado em contrato.";
  doc.text(obs, margin + 3, cursorY + 10, { maxWidth: pageW - margin * 2 - 6 });

  if (nota.cartasCorrecao && nota.cartasCorrecao.length > 0) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(7);
    doc.text(
      `${nota.cartasCorrecao.length} carta(s) de correção emitida(s)`,
      margin + 3,
      cursorY + 18
    );
  }

  cursorY = pageH - 8;
  doc.setFontSize(7);
  doc.setTextColor(150, 150, 150);
  doc.text(
    "DANFE gerado pelo FiscalAI · ambiente de demonstração · não tem validade fiscal",
    pageW / 2,
    cursorY,
    { align: "center" }
  );

  return doc;
}

function campo(
  doc: jsPDF,
  x: number,
  y: number,
  label: string,
  valor: string,
  size = 11
) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text(label, x, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(size);
  doc.setTextColor(20, 20, 20);
  doc.text(valor, x, y + 6);
}

function campoMini(
  doc: jsPDF,
  x: number,
  y: number,
  label: string,
  valor: string
) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(6.5);
  doc.setTextColor(120, 120, 120);
  doc.text(label, x, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(20, 20, 20);
  doc.text(valor, x, y + 6);
}

function formatarNumeroNFe(num: string): string {
  const n = num.padStart(9, "0");
  return `${n.slice(0, 3)}.${n.slice(3, 6)}.${n.slice(6, 9)}`;
}

export function nomeArquivoDANFE(nota: NotaFiscal): string {
  return `DANFE-${nota.numero}.pdf`;
}
