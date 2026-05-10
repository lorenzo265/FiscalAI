export interface BancoOpenFinance {
  id: string;
  nome: string;
  apelido: string;
  cor: string;
  textoCor: string;
  iniciais: string;
}

export const BANCOS_OPENFINANCE: BancoOpenFinance[] = [
  {
    id: "itau",
    nome: "Itaú",
    apelido: "Itaú Unibanco",
    cor: "#EC7000",
    textoCor: "#06080f",
    iniciais: "Itaú",
  },
  {
    id: "bradesco",
    nome: "Bradesco",
    apelido: "Bradesco S.A.",
    cor: "#CC092F",
    textoCor: "#ffffff",
    iniciais: "BRA",
  },
  {
    id: "bb",
    nome: "Banco do Brasil",
    apelido: "BB",
    cor: "#FFEF38",
    textoCor: "#0033A0",
    iniciais: "BB",
  },
  {
    id: "santander",
    nome: "Santander",
    apelido: "Santander BR",
    cor: "#EC0000",
    textoCor: "#ffffff",
    iniciais: "SAN",
  },
  {
    id: "nubank",
    nome: "Nubank",
    apelido: "Nu Pagamentos",
    cor: "#820AD1",
    textoCor: "#ffffff",
    iniciais: "Nu",
  },
  {
    id: "inter",
    nome: "Inter",
    apelido: "Banco Inter",
    cor: "#FF7A00",
    textoCor: "#ffffff",
    iniciais: "Inter",
  },
];
