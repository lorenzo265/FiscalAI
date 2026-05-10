import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Contraparte,
  ItemNota,
  ProdutoCatalogo,
  TotaisNota,
} from "@/lib/schemas/nota";

interface EntradaItem {
  produto?: ProdutoCatalogo;
  descricao: string;
  unidade?: string;
  quantidade: number;
  valorUnitario: number;
  ncm?: string;
  cfop?: string;
}

const ALIQUOTAS_ICMS_INTERNO: Record<string, number> = {
  RS: 0.17,
  SC: 0.17,
  PR: 0.18,
  SP: 0.18,
  RJ: 0.2,
  MG: 0.18,
  ES: 0.17,
  BA: 0.18,
  PE: 0.18,
  CE: 0.18,
  GO: 0.17,
  DF: 0.18,
};

const ALIQUOTAS_ICMS_INTERESTADUAL: Record<string, number> = {
  // origem -> destino simplificado (Sul/Sudeste para outras regiões = 7%, demais = 12%)
  default: 0.12,
};

export function calcularImpostosItem({
  empresa,
  contraparte,
  entrada,
}: {
  empresa: Pick<Empresa, "regime" | "uf" | "anexoSimples">;
  contraparte: Pick<Contraparte, "tipo" | "endereco">;
  entrada: EntradaItem;
}): ItemNota {
  const valorTotal = round2(entrada.quantidade * entrada.valorUnitario);
  const isServico = entrada.produto?.tipo === "servico" || !entrada.produto;
  const ncm = entrada.ncm ?? entrada.produto?.ncm ?? (isServico ? "00000000" : "00000000");
  const cfopBase = entrada.cfop ?? entrada.produto?.cfop ?? (isServico ? "5933" : "5102");

  const ufDestino = contraparte.endereco?.uf ?? empresa.uf;
  const interestadual = ufDestino !== empresa.uf;
  const cfop = ajustarCfop(cfopBase, interestadual);

  if (isServico) {
    const aliquotaIss = aliquotaIssPorMunicipio();
    const aliquotaPis = empresa.regime === "SIMPLES_NACIONAL" ? 0 : 0.0065;
    const aliquotaCofins = empresa.regime === "SIMPLES_NACIONAL" ? 0 : 0.03;
    const iss = round2(valorTotal * aliquotaIss);
    const pis = round2(valorTotal * aliquotaPis);
    const cofins = round2(valorTotal * aliquotaCofins);
    return {
      id: pseudoId(),
      produtoId: entrada.produto?.id,
      descricao: entrada.descricao,
      unidade: entrada.unidade ?? entrada.produto?.unidade ?? "UN",
      quantidade: entrada.quantidade,
      valorUnitario: round2(entrada.valorUnitario),
      valorTotal,
      ncm,
      cfop,
      cstCsosn: cstParaRegime(empresa.regime),
      aliquotaIss,
      aliquotaPis,
      aliquotaCofins,
      impostoTotal: round2(iss + pis + cofins),
    };
  }

  const aliquotaIcms = interestadual
    ? (ALIQUOTAS_ICMS_INTERESTADUAL[`${empresa.uf}-${ufDestino}`] ??
        ALIQUOTAS_ICMS_INTERESTADUAL.default!)
    : (ALIQUOTAS_ICMS_INTERNO[empresa.uf] ?? 0.18);
  const aliquotaPis = empresa.regime === "SIMPLES_NACIONAL" ? 0 : 0.0165;
  const aliquotaCofins = empresa.regime === "SIMPLES_NACIONAL" ? 0 : 0.076;

  const icms = round2(valorTotal * aliquotaIcms);
  const pis = round2(valorTotal * aliquotaPis);
  const cofins = round2(valorTotal * aliquotaCofins);

  return {
    id: pseudoId(),
    produtoId: entrada.produto?.id,
    descricao: entrada.descricao,
    unidade: entrada.unidade ?? entrada.produto?.unidade ?? "UN",
    quantidade: entrada.quantidade,
    valorUnitario: round2(entrada.valorUnitario),
    valorTotal,
    ncm,
    cfop,
    cstCsosn: cstParaRegime(empresa.regime),
    aliquotaIcms,
    aliquotaPis,
    aliquotaCofins,
    impostoTotal: round2(icms + pis + cofins),
  };
}

export function totalizarNota(itens: ItemNota[]): TotaisNota {
  let produtos = 0;
  let icms = 0;
  let iss = 0;
  let pis = 0;
  let cofins = 0;
  for (const it of itens) {
    produtos += it.valorTotal;
    if (it.aliquotaIcms) icms += it.valorTotal * it.aliquotaIcms;
    if (it.aliquotaIss) iss += it.valorTotal * it.aliquotaIss;
    if (it.aliquotaPis) pis += it.valorTotal * it.aliquotaPis;
    if (it.aliquotaCofins) cofins += it.valorTotal * it.aliquotaCofins;
  }
  const totalImpostos = icms + iss + pis + cofins;
  return {
    produtos: round2(produtos),
    desconto: 0,
    frete: 0,
    icms: round2(icms),
    iss: round2(iss),
    pis: round2(pis),
    cofins: round2(cofins),
    totalImpostos: round2(totalImpostos),
    valorNota: round2(produtos),
  };
}

function ajustarCfop(cfop: string, interestadual: boolean): string {
  if (cfop.length !== 4) return cfop;
  if (interestadual) {
    return "6" + cfop.slice(1);
  }
  return cfop;
}

function cstParaRegime(regime: Empresa["regime"]): string {
  if (regime === "SIMPLES_NACIONAL" || regime === "MEI") return "102";
  return "00";
}

function aliquotaIssPorMunicipio(): number {
  return 0.05;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function pseudoId(): string {
  return Math.random().toString(36).slice(2, 10);
}
