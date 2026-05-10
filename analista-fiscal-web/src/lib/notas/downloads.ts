import type { NotaFiscal } from "@/lib/schemas/nota";
import { gerarXmlNFe, nomeArquivoXml } from "@/lib/notas/xml";

export async function baixarDANFE(nota: NotaFiscal): Promise<void> {
  const { gerarPdfDANFE, nomeArquivoDANFE } = await import("@/lib/pdf/danfe");
  const doc = gerarPdfDANFE(nota);
  doc.save(nomeArquivoDANFE(nota));
}

export function baixarXml(nota: NotaFiscal): void {
  const xml = gerarXmlNFe(nota);
  const blob = new Blob([xml], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivoXml(nota.chave);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
