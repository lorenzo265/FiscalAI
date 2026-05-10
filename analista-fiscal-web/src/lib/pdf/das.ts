import { jsPDF } from "jspdf";
import JsBarcode from "jsbarcode";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";

export interface DadosGuiaDAS {
  empresa: {
    razaoSocial: string;
    cnpj: string;
  };
  periodo: { ano: number; mes: number };
  faturamentoMes: number;
  aliquotaEfetiva: number;
  valorDAS: number;
  vencimento: string;
  codigoBarras: string;
  numeroDocumento: string;
}

export function gerarPdfDAS(dados: DadosGuiaDAS): jsPDF {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 14;

  doc.setFillColor(6, 8, 15);
  doc.rect(0, 0, pageW, 32, "F");

  doc.setTextColor(163, 255, 107);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.text("FiscalAI", margin, 16);

  doc.setTextColor(221, 227, 240);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.text("Guia DAS — Documento de Arrecadação do Simples Nacional", margin, 23);
  doc.setFontSize(8);
  doc.setTextColor(136, 146, 168);
  doc.text("Documento mock gerado para fins de demonstração", margin, 28);

  doc.setTextColor(20, 20, 20);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("CONTRIBUINTE", margin, 44);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.text(dados.empresa.razaoSocial, margin, 50);
  doc.setFontSize(10);
  doc.setTextColor(80, 80, 80);
  doc.text(`CNPJ ${formatarCNPJ(dados.empresa.cnpj)}`, margin, 56);

  const boxY = 62;
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.3);
  doc.rect(margin, boxY, pageW - margin * 2, 38);

  const colW = (pageW - margin * 2) / 3;
  desenharCampo(
    doc,
    margin + 4,
    boxY + 6,
    "Período de apuração",
    nomeMes(dados.periodo.mes) + "/" + dados.periodo.ano
  );
  desenharCampo(
    doc,
    margin + 4 + colW,
    boxY + 6,
    "Receita do mês",
    formatarMoeda(dados.faturamentoMes)
  );
  desenharCampo(
    doc,
    margin + 4 + colW * 2,
    boxY + 6,
    "Alíquota efetiva",
    `${(dados.aliquotaEfetiva * 100).toFixed(2).replace(".", ",")}%`
  );

  desenharCampo(
    doc,
    margin + 4,
    boxY + 22,
    "Vencimento",
    formatarDataBR(dados.vencimento)
  );
  desenharCampo(
    doc,
    margin + 4 + colW,
    boxY + 22,
    "Documento",
    dados.numeroDocumento
  );

  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text("VALOR A PAGAR", margin + 4 + colW * 2, boxY + 26);
  doc.setFontSize(20);
  doc.setTextColor(0, 0, 0);
  doc.text(formatarMoeda(dados.valorDAS), margin + 4 + colW * 2, boxY + 34);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(20, 20, 20);
  doc.text("CÓDIGO DE BARRAS", margin, boxY + 52);

  try {
    const canvas =
      typeof document !== "undefined" ? document.createElement("canvas") : null;
    if (canvas) {
      JsBarcode(canvas, dados.codigoBarras, {
        format: "CODE128",
        width: 1.4,
        height: 60,
        displayValue: false,
        margin: 0,
      });
      const imgData = canvas.toDataURL("image/png");
      doc.addImage(imgData, "PNG", margin, boxY + 56, pageW - margin * 2, 22);
    }
  } catch (err) {
    console.warn("Não foi possível gerar barcode:", err);
  }

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(20, 20, 20);
  const codigoFormatado = dados.codigoBarras
    .replace(/(\d{4})/g, "$1 ")
    .trim();
  doc.text(codigoFormatado, margin, boxY + 84);

  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  doc.text(
    "Documento gerado pelo FiscalAI · Demo. Não tem validade fiscal.",
    margin,
    285
  );

  return doc;
}

function desenharCampo(
  doc: jsPDF,
  x: number,
  y: number,
  label: string,
  valor: string
) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text(label.toUpperCase(), x, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(20, 20, 20);
  doc.text(valor, x, y + 6);
}

function nomeMes(mes: number): string {
  const meses = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
  ];
  return meses[mes - 1] ?? "—";
}

export function nomeArquivoDAS(periodo: { ano: number; mes: number }): string {
  const mm = String(periodo.mes).padStart(2, "0");
  return `DAS-${mm}-${periodo.ano}.pdf`;
}
