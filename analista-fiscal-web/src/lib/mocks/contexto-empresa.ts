import type { Empresa, AnexoSimples, RegimeTributario } from "@/lib/schemas/empresa";

export interface ContextoEmpresaMock {
  cnpj: string;
  razaoSocial: string;
  regime: RegimeTributario;
  anexoSimples?: AnexoSimples;
  faturamento12m: number;
  uf: string;
}

export function lerContexto(searchParams: URLSearchParams): ContextoEmpresaMock {
  const cnpj = searchParams.get("cnpj") ?? "12345678000199";
  const regime = (searchParams.get("regime") ?? "SIMPLES_NACIONAL") as RegimeTributario;
  const anexo = (searchParams.get("anexo") ?? "III") as AnexoSimples;
  const fat = Number(searchParams.get("fat12") ?? "850000");
  const uf = searchParams.get("uf") ?? "RS";
  const razao = searchParams.get("razao") ?? "FiscalAI Demo Ltda";
  return {
    cnpj,
    razaoSocial: razao,
    regime,
    anexoSimples: anexo,
    faturamento12m: Number.isFinite(fat) ? fat : 850000,
    uf,
  };
}

export function contextoComoEmpresa(c: ContextoEmpresaMock): Empresa {
  return {
    id: "ctx-mock",
    cnpj: c.cnpj,
    razaoSocial: c.razaoSocial,
    regime: c.regime,
    anexoSimples: c.anexoSimples,
    setor: "SERVICOS",
    cnae: "0000-0/00",
    uf: c.uf,
    municipio: "—",
    faturamento12m: c.faturamento12m,
    socios: [],
    bancosConectados: [],
    modulosAtivos: [],
    criadoEm: new Date().toISOString(),
  };
}
