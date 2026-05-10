import type { Empresa } from "@/lib/schemas/empresa";

export const EMPRESA_DEMO_ID = "empresa-demo";
export const EMPRESA_DEMO_CNPJ = "12345678000199";

export function criarEmpresaDemo(): Empresa {
  return {
    id: EMPRESA_DEMO_ID,
    cnpj: EMPRESA_DEMO_CNPJ,
    razaoSocial: "FiscalAI Demo Ltda",
    nomeFantasia: "FiscalAI Demo",
    regime: "SIMPLES_NACIONAL",
    anexoSimples: "III",
    setor: "SERVICOS",
    cnae: "6201-5/01",
    uf: "RS",
    municipio: "Porto Alegre",
    inscricaoEstadual: "ISENTO",
    inscricaoMunicipal: "98765432",
    faturamento12m: 850_000,
    socios: [
      { cpf: "11122233344", nome: "Maria Silva", participacao: 60, isAdministrador: true },
      { cpf: "55566677788", nome: "João Santos", participacao: 40, isAdministrador: false },
    ],
    certificadoA1: {
      nomeArquivo: "fiscalai-demo.pfx",
      validade: "2027-05-08",
      mock: true,
    },
    bancosConectados: [
      {
        id: "banco-itau",
        banco: "Itaú",
        apelido: "Conta Principal",
        saldo: 142_580.33,
        ultimaSync: new Date().toISOString(),
      },
      {
        id: "banco-nubank",
        banco: "Nubank",
        apelido: "Reserva",
        saldo: 38_220.5,
        ultimaSync: new Date().toISOString(),
      },
      {
        id: "banco-bradesco",
        banco: "Bradesco",
        apelido: "Folha",
        saldo: 12_990.0,
        ultimaSync: new Date().toISOString(),
      },
    ],
    modulosAtivos: [
      "fiscal",
      "notas",
      "contabil",
      "controles",
      "pessoal",
      "relatorios",
      "compliance",
      "agenda",
      "assistente",
      "configuracoes",
    ],
    criadoEm: new Date().toISOString(),
  };
}
