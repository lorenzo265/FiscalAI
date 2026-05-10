import type { CnpjLookupResponse } from "@/lib/schemas/cnpj-lookup";
import { apenasDigitos } from "@/lib/format/cnpj";

const RAZOES = [
  "Soluções Digitais Ltda",
  "Lumen Estúdio Criativo Ltda",
  "Verde Distribuidora Ltda",
  "Alpha Engenharia ME",
  "Boutique Bossa Ltda",
  "Mares Comércio de Alimentos Ltda",
];

const FANTASIAS = [
  "Soluções Digitais",
  "Lumen Estúdio",
  "Verde Distribuidora",
  "Alpha Engenharia",
  "Boutique Bossa",
  "Mares Alimentos",
];

const CNAES = [
  { codigo: "6201-5/01", descricao: "Desenvolvimento de programas de computador sob encomenda" },
  { codigo: "4711-3/02", descricao: "Comércio varejista de mercadorias em geral - supermercado" },
  { codigo: "4781-4/00", descricao: "Comércio varejista de artigos do vestuário e acessórios" },
  { codigo: "5611-2/01", descricao: "Restaurantes e similares" },
  { codigo: "7020-4/00", descricao: "Atividades de consultoria em gestão empresarial" },
];

const ESTADOS = ["RS", "SP", "MG", "PR", "SC", "RJ"];
const MUNICIPIOS: Record<string, string> = {
  RS: "Porto Alegre",
  SP: "São Paulo",
  MG: "Belo Horizonte",
  PR: "Curitiba",
  SC: "Florianópolis",
  RJ: "Rio de Janeiro",
};

function pickByDigits<T>(arr: readonly T[], cnpj: string): T {
  const digits = apenasDigitos(cnpj);
  const seed = digits.split("").reduce((acc, d) => acc + Number(d), 0);
  const item = arr[seed % arr.length];
  return item as T;
}

export function gerarCnpjLookupMock(cnpj: string): CnpjLookupResponse {
  const digits = apenasDigitos(cnpj).padStart(14, "0").slice(-14);
  const razao = pickByDigits(RAZOES, digits);
  const fantasia = pickByDigits(FANTASIAS, digits);
  const principal = pickByDigits(CNAES, digits);
  const uf = pickByDigits(ESTADOS, digits) as keyof typeof MUNICIPIOS;
  const municipio = MUNICIPIOS[uf] ?? "Porto Alegre";

  const secundarios = CNAES.filter((c) => c.codigo !== principal.codigo).slice(0, 2);

  return {
    cnpj: digits,
    razaoSocial: razao,
    nomeFantasia: fantasia,
    cnaePrincipal: principal,
    cnaesSecundarios: secundarios,
    endereco: {
      logradouro: "Av. das Indústrias",
      numero: String(100 + (Number(digits.slice(-3)) % 900)),
      complemento: "Sala 502",
      bairro: "Centro",
      municipio,
      uf,
      cep: `${digits.slice(0, 5)}-${digits.slice(5, 8)}`,
    },
    porte: "ME — Microempresa",
    situacao: "ATIVA",
    dataAbertura: "2022-08-15",
    socios: [
      {
        cpf: "11122233344",
        nome: "Maria Silva",
        participacao: 60,
        isAdministrador: true,
      },
      {
        cpf: "55566677788",
        nome: "João Santos",
        participacao: 40,
        isAdministrador: false,
      },
    ],
  };
}
