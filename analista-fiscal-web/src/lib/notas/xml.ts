import type { NotaFiscal } from "@/lib/schemas/nota";
import { apenasDigitos } from "@/lib/format/cnpj";

export function gerarXmlNFe(nota: NotaFiscal): string {
  const chave = nota.chave;
  const cUF = chave.slice(0, 2);
  const dest = nota.contraparte;
  const docDest = apenasDigitos(dest.documento);
  const itensXml = nota.itens
    .map((it, i) => itemXml(it, i + 1))
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe${chave}" versao="4.00">
      <ide>
        <cUF>${cUF}</cUF>
        <natOp>${escapeXml(natOp(nota))}</natOp>
        <mod>55</mod>
        <serie>${nota.serie}</serie>
        <nNF>${nota.numero}</nNF>
        <dhEmi>${nota.emitidaEm}</dhEmi>
        <tpNF>${nota.tipo === "saida" ? "1" : "0"}</tpNF>
      </ide>
      <emit>
        <CNPJ>${apenasDigitos(nota.cnpjEmitente)}</CNPJ>
        <xNome>${escapeXml(nota.razaoEmitente)}</xNome>
      </emit>
      <dest>
        ${dest.tipo === "pj" ? `<CNPJ>${docDest}</CNPJ>` : `<CPF>${docDest}</CPF>`}
        <xNome>${escapeXml(dest.nome)}</xNome>
      </dest>
${itensXml}
      <total>
        <ICMSTot>
          <vBC>0.00</vBC>
          <vICMS>${nota.totais.icms.toFixed(2)}</vICMS>
          <vPIS>${nota.totais.pis.toFixed(2)}</vPIS>
          <vCOFINS>${nota.totais.cofins.toFixed(2)}</vCOFINS>
          <vNF>${nota.totais.valorNota.toFixed(2)}</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
  ${nota.protocoloAutorizacao ? `<protNFe versao="4.00"><infProt><nProt>${nota.protocoloAutorizacao}</nProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>` : ""}
</nfeProc>`;
}

function natOp(nota: NotaFiscal): string {
  return nota.tipo === "saida" ? "Venda de mercadoria/serviço" : "Entrada";
}

function itemXml(it: NotaFiscal["itens"][number], n: number): string {
  return `      <det nItem="${n}">
        <prod>
          <cProd>${escapeXml(it.produtoId ?? `ITEM${n}`)}</cProd>
          <xProd>${escapeXml(it.descricao)}</xProd>
          <NCM>${it.ncm}</NCM>
          <CFOP>${it.cfop}</CFOP>
          <uCom>${it.unidade}</uCom>
          <qCom>${it.quantidade.toFixed(4)}</qCom>
          <vUnCom>${it.valorUnitario.toFixed(4)}</vUnCom>
          <vProd>${it.valorTotal.toFixed(2)}</vProd>
        </prod>
      </det>`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function nomeArquivoXml(chave: string): string {
  return `${chave}-nfe.xml`;
}
