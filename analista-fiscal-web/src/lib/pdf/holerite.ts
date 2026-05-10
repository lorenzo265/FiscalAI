import { jsPDF } from "jspdf";
import { formatarCNPJ } from "@/lib/format/cnpj";
import { formatarCPF } from "@/lib/format/cpf";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import type { Holerite } from "@/lib/schemas/pessoal";
import type { Empresa } from "@/lib/schemas/empresa";
import type { Funcionario } from "@/lib/schemas/pessoal";

interface DadosHolerite {
  empresa: Pick<Empresa, "razaoSocial" | "cnpj">;
  funcionario: Pick<
    Funcionario,
    "nome" | "cpf" | "cargo" | "dataAdmissao" | "pisPasep"
  >;
  holerite: Holerite;
}

const NOMES_MES = [
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

export function gerarPdfHolerite(dados: DadosHolerite): jsPDF {
  const { empresa, funcionario, holerite } = dados;
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 14;

  // Header
  doc.setFillColor(6, 8, 15);
  doc.rect(0, 0, pageW, 30, "F");
  doc.setTextColor(163, 255, 107);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("FiscalAI", margin, 15);
  doc.setTextColor(221, 227, 240);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text("Recibo de Pagamento de Salário", margin, 22);
  doc.setFontSize(8);
  doc.setTextColor(136, 146, 168);
  doc.text("Documento mock — sem validade fiscal", margin, 27);

  // Empresa
  doc.setTextColor(20, 20, 20);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.text("EMPREGADOR", margin, 40);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(empresa.razaoSocial, margin, 46);
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text(`CNPJ ${formatarCNPJ(empresa.cnpj)}`, margin, 51);

  // Competência box
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.3);
  doc.rect(pageW - margin - 60, 36, 60, 18);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(120, 120, 120);
  doc.text("COMPETÊNCIA", pageW - margin - 56, 41);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(12);
  doc.setTextColor(20, 20, 20);
  doc.text(
    `${NOMES_MES[holerite.mes - 1]}/${holerite.ano}`,
    pageW - margin - 56,
    49
  );

  // Funcionario
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(20, 20, 20);
  doc.text("FUNCIONÁRIO", margin, 60);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(funcionario.nome, margin, 66);
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  const linhaInfo = [
    `CPF ${formatarCPF(funcionario.cpf)}`,
    funcionario.pisPasep ? `PIS ${funcionario.pisPasep}` : null,
    funcionario.cargo,
    `Admissão ${formatarDataBR(funcionario.dataAdmissao)}`,
  ]
    .filter(Boolean)
    .join("    ·    ");
  doc.text(linhaInfo, margin, 71);

  // Tabela de eventos
  const tabelaY = 80;
  desenharCabecalhoTabela(doc, margin, tabelaY, pageW);

  let y = tabelaY + 8;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(30, 30, 30);

  for (const evento of holerite.eventos) {
    if (y > 240) {
      doc.addPage();
      y = 30;
      desenharCabecalhoTabela(doc, margin, y - 8, pageW);
    }
    desenharLinhaEvento(doc, margin, y, pageW, evento);
    y += 6;
  }

  // Totais
  const totaisY = Math.max(y + 4, 200);
  doc.setDrawColor(220, 220, 220);
  doc.line(margin, totaisY, pageW - margin, totaisY);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.setTextColor(80, 80, 80);
  doc.text("TOTAL DE PROVENTOS", margin, totaisY + 8);
  doc.text("TOTAL DE DESCONTOS", margin + (pageW - margin * 2) / 3, totaisY + 8);

  doc.setFontSize(12);
  doc.setTextColor(0, 90, 0);
  doc.text(formatarMoeda(holerite.totalProventos), margin, totaisY + 15);
  doc.setTextColor(150, 0, 0);
  doc.text(
    formatarMoeda(holerite.totalDescontos),
    margin + (pageW - margin * 2) / 3,
    totaisY + 15
  );

  // Líquido
  doc.setFillColor(245, 247, 250);
  doc.rect(pageW - margin - 70, totaisY + 2, 70, 22, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(80, 80, 80);
  doc.text("LÍQUIDO A RECEBER", pageW - margin - 66, totaisY + 9);
  doc.setFontSize(16);
  doc.setTextColor(0, 0, 0);
  doc.text(
    formatarMoeda(holerite.totalLiquido),
    pageW - margin - 66,
    totaisY + 19
  );

  // Bases
  const basesY = totaisY + 32;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  doc.text("BASE INSS", margin, basesY);
  doc.text("BASE FGTS", margin + 50, basesY);
  doc.text("BASE IRRF", margin + 100, basesY);
  doc.text("FGTS DO MÊS", margin + 150, basesY);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(30, 30, 30);
  doc.text(formatarMoeda(holerite.baseInss), margin, basesY + 6);
  doc.text(formatarMoeda(holerite.baseFgts), margin + 50, basesY + 6);
  doc.text(formatarMoeda(holerite.baseIrrf), margin + 100, basesY + 6);
  doc.text(formatarMoeda(holerite.fgts), margin + 150, basesY + 6);

  // Footer
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  doc.text(
    "Recibo gerado pelo FiscalAI — assine ao receber. Documento de demonstração.",
    margin,
    285
  );

  return doc;
}

function desenharCabecalhoTabela(
  doc: jsPDF,
  margin: number,
  y: number,
  pageW: number
) {
  doc.setFillColor(245, 247, 250);
  doc.rect(margin, y, pageW - margin * 2, 6, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(80, 80, 80);
  doc.text("CÓD", margin + 2, y + 4);
  doc.text("DESCRIÇÃO", margin + 16, y + 4);
  doc.text("REFERÊNCIA", margin + 100, y + 4);
  doc.text("PROVENTOS", pageW - margin - 50, y + 4, { align: "right" });
  doc.text("DESCONTOS", pageW - margin - 4, y + 4, { align: "right" });
}

function desenharLinhaEvento(
  doc: jsPDF,
  margin: number,
  y: number,
  pageW: number,
  evento: Holerite["eventos"][number]
) {
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(30, 30, 30);
  doc.text(evento.codigo, margin + 2, y);
  doc.text(evento.descricao, margin + 16, y);
  doc.text(evento.referencia, margin + 100, y);
  if (evento.tipo === "provento") {
    doc.text(formatarMoeda(evento.valor), pageW - margin - 50, y, {
      align: "right",
    });
    doc.text("—", pageW - margin - 4, y, { align: "right" });
  } else {
    doc.text("—", pageW - margin - 50, y, { align: "right" });
    doc.text(formatarMoeda(evento.valor), pageW - margin - 4, y, {
      align: "right",
    });
  }
}

export function nomeArquivoHolerite(holerite: Holerite): string {
  const mm = String(holerite.mes).padStart(2, "0");
  const slug = holerite.funcionarioNome
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `holerite-${slug}-${mm}-${holerite.ano}.pdf`;
}
