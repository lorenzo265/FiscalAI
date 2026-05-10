// Geração de chave de acesso NF-e (44 dígitos) — versão mock determinística.
// Layout oficial: cUF(2) + AAMM(4) + CNPJ(14) + mod(2) + serie(3) + nNF(9) + tpEmis(1) + cNF(8) + cDV(1)

import { apenasDigitos } from "@/lib/format/cnpj";

const UF_CODIGO: Record<string, string> = {
  AC: "12",
  AL: "27",
  AM: "13",
  AP: "16",
  BA: "29",
  CE: "23",
  DF: "53",
  ES: "32",
  GO: "52",
  MA: "21",
  MG: "31",
  MS: "50",
  MT: "51",
  PA: "15",
  PB: "25",
  PE: "26",
  PI: "22",
  PR: "41",
  RJ: "33",
  RN: "24",
  RO: "11",
  RR: "14",
  RS: "43",
  SC: "42",
  SE: "28",
  SP: "35",
  TO: "17",
};

export function montarChaveNFe(params: {
  uf: string;
  ano: number;
  mes: number;
  cnpj: string;
  modelo?: string;
  serie?: string;
  numero: number;
  codigoNumerico?: string;
}): string {
  const cUF = UF_CODIGO[params.uf.toUpperCase()] ?? "35";
  const aamm = `${String(params.ano).slice(-2)}${String(params.mes).padStart(2, "0")}`;
  const cnpj = apenasDigitos(params.cnpj).padStart(14, "0").slice(-14);
  const mod = (params.modelo ?? "55").padStart(2, "0");
  const serie = (params.serie ?? "001").padStart(3, "0");
  const num = String(params.numero).padStart(9, "0");
  const tpEmis = "1";
  const cNF =
    params.codigoNumerico ??
    String(Math.abs(hashSimples(`${cnpj}-${num}-${aamm}`)) % 100_000_000)
      .padStart(8, "0");

  const semDV = `${cUF}${aamm}${cnpj}${mod}${serie}${num}${tpEmis}${cNF}`;
  const dv = calcularDV(semDV);
  return semDV + dv;
}

export function formatarChave(chave: string): string {
  return apenasDigitos(chave).slice(0, 44).replace(/(\d{4})/g, "$1 ").trim();
}

function calcularDV(chave43: string): string {
  const pesos = [2, 3, 4, 5, 6, 7, 8, 9];
  let soma = 0;
  for (let i = 0; i < chave43.length; i++) {
    const d = Number(chave43[chave43.length - 1 - i]);
    soma += d * pesos[i % pesos.length]!;
  }
  const resto = soma % 11;
  const dv = resto < 2 ? 0 : 11 - resto;
  return String(dv);
}

function hashSimples(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return h;
}
