import type { Empresa } from "@/lib/schemas/empresa";
import type {
  CategoriaConta,
  CategoriaTransacao,
  ContaBancaria,
  ContaPagarReceber,
  FluxoCaixa,
  FluxoCaixaPonto,
  StatusContaPagarReceber,
  TipoTransacao,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import {
  BANCOS_OPENFINANCE,
  type BancoOpenFinance,
} from "@/lib/mocks/seeds/bancos-openfinance";
import { pseudoUuid } from "@/lib/mocks/utils";

const CONTRAPARTES_TRANSACAO = [
  "Mercado Atacadão",
  "Hortifrúti Bom Preço",
  "Cerveja União Distrib.",
  "Frigorífico Sul",
  "Padaria Estrela",
  "CEEE Energia",
  "Vivo Empresas",
  "Aluguel Imobiliária Forte",
  "Coca-Cola FEMSA",
  "Distribuidora Bebidas Polar",
  "Cliente PIX particular",
  "Boleto recebido",
];

const RANDOM_DESCRICOES_DEBITO: Record<CategoriaTransacao, string[]> = {
  receita_vendas: [],
  recebimento_cliente: [],
  pagamento_fornecedor: [
    "Pagamento fornecedor",
    "Boleto fornecedor",
    "Compra a prazo",
  ],
  folha_pagamento: ["Folha de pagamento", "Pagamento de salário"],
  tributos: ["DAS Simples", "ISS municipal", "Tributo federal"],
  tarifas_bancarias: ["Tarifa cesta de serviços", "TED enviada", "Manut. conta"],
  transferencia: ["Transferência interna"],
  estorno: ["Estorno débito"],
  rendimento: [],
  outros: ["Pagamento diverso"],
};

const RANDOM_DESCRICOES_CREDITO: Record<CategoriaTransacao, string[]> = {
  receita_vendas: ["PIX recebido — venda", "Cartão de crédito (D+30)"],
  recebimento_cliente: ["Boleto pago por cliente", "PIX cliente"],
  pagamento_fornecedor: [],
  folha_pagamento: [],
  tributos: [],
  tarifas_bancarias: [],
  transferencia: ["Transferência recebida"],
  estorno: ["Estorno crédito"],
  rendimento: ["Rendimento aplicação"],
  outros: ["Recebimento diverso"],
};

const CATEGORIAS_DEBITO: CategoriaTransacao[] = [
  "pagamento_fornecedor",
  "pagamento_fornecedor",
  "pagamento_fornecedor",
  "folha_pagamento",
  "tributos",
  "tarifas_bancarias",
  "outros",
];
const CATEGORIAS_CREDITO: CategoriaTransacao[] = [
  "receita_vendas",
  "receita_vendas",
  "receita_vendas",
  "recebimento_cliente",
  "rendimento",
];

interface RngState {
  seed: number;
}

function mulberry32(seed: number) {
  let s = seed >>> 0;
  return function rand() {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seedFromCnpj(cnpj: string, sufixo = 0): number {
  const limpo = cnpj.replace(/\D/g, "");
  let h = 2166136261;
  for (let i = 0; i < limpo.length; i++) {
    h ^= limpo.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h + sufixo * 7919) >>> 0;
}

function pickFrom<T>(arr: readonly T[], rand: () => number): T {
  const item = arr[Math.floor(rand() * arr.length)];
  if (item === undefined) {
    throw new Error("array vazio em pickFrom");
  }
  return item;
}

function arredondar(n: number, casas = 2): number {
  const f = 10 ** casas;
  return Math.round(n * f) / f;
}

const DIA_MS = 24 * 60 * 60 * 1000;

function isoDia(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function bancoSeed(id: string): BancoOpenFinance {
  return (
    BANCOS_OPENFINANCE.find((b) => b.id === id) ??
    BANCOS_OPENFINANCE[0]!
  );
}

export function gerarContasIniciais(empresa: Empresa): ContaBancaria[] {
  const bancos = ["itau", "nubank", "bradesco"];
  const rand = mulberry32(seedFromCnpj(empresa.cnpj, 1));
  const hoje = new Date();

  return bancos.map((bid, i) => {
    const banco = bancoSeed(bid);
    const saldoBase = 35_000 + rand() * 90_000;
    const saldo = arredondar(saldoBase * (i === 0 ? 1.4 : 1));
    return {
      id: `conta-${empresa.id}-${bid}`,
      bancoId: banco.id,
      bancoNome: banco.nome,
      apelido: `${banco.nome} · Conta principal`,
      agencia: String(1000 + Math.floor(rand() * 8999)).padStart(4, "0"),
      numero: `${String(10000 + Math.floor(rand() * 89999))}-${Math.floor(rand() * 9)}`,
      saldo,
      cor: banco.cor,
      textoCor: banco.textoCor,
      iniciais: banco.iniciais,
      conectadaEm: new Date(hoje.getTime() - (60 + i * 30) * DIA_MS).toISOString(),
      ultimoSyncEm: new Date(hoje.getTime() - (i + 1) * 30 * 60 * 1000).toISOString(),
    } satisfies ContaBancaria;
  });
}

export function gerarTransacoesIniciais(
  conta: ContaBancaria,
  dias = 60
): TransacaoBancaria[] {
  const rand = mulberry32(seedFromCnpj(conta.id, 2));
  const transacoes: TransacaoBancaria[] = [];
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  let saldo = conta.saldo;
  // Vamos gerar do mais recente para o mais antigo, depois inverter pra calcular saldoApos
  const movimentos: Array<Omit<TransacaoBancaria, "saldoApos">> = [];

  for (let d = 0; d < dias; d++) {
    const data = new Date(hoje.getTime() - d * DIA_MS);
    const diaSemana = data.getDay();
    if (diaSemana === 0) continue; // pula domingos
    const qtd = 1 + Math.floor(rand() * 4);
    for (let k = 0; k < qtd; k++) {
      const credito = rand() < 0.55;
      const tipo: TipoTransacao = credito ? "credito" : "debito";
      const categoria = credito
        ? pickFrom(CATEGORIAS_CREDITO, rand)
        : pickFrom(CATEGORIAS_DEBITO, rand);
      const descricoes = credito
        ? RANDOM_DESCRICOES_CREDITO[categoria]
        : RANDOM_DESCRICOES_DEBITO[categoria];
      const descricao =
        descricoes.length > 0 ? pickFrom(descricoes, rand) : "Movimento";
      const contraparte = pickFrom(CONTRAPARTES_TRANSACAO, rand);
      const valorBase = credito
        ? 200 + rand() * 4_500
        : 80 + rand() * 2_400;
      const valor = arredondar(valorBase);
      movimentos.push({
        id: `tx-${conta.id}-${d}-${k}-${pseudoUuid().slice(0, 6)}`,
        contaId: conta.id,
        data: isoDia(data),
        descricao,
        contraparte,
        valor,
        tipo,
        categoria,
        conciliada: rand() < 0.65,
      });
    }
  }

  // Ordena cronologicamente (do mais antigo) e calcula saldoApos retroativamente
  movimentos.sort((a, b) => a.data.localeCompare(b.data));

  // Estima saldo no início da janela (saldo atual menos efeito líquido)
  const liquido = movimentos.reduce(
    (acc, m) => acc + (m.tipo === "credito" ? m.valor : -m.valor),
    0
  );
  saldo = arredondar(conta.saldo - liquido);
  for (const m of movimentos) {
    saldo = arredondar(saldo + (m.tipo === "credito" ? m.valor : -m.valor));
    transacoes.push({ ...m, saldoApos: saldo });
  }
  return transacoes;
}

export function gerarContasPagarReceberIniciais(
  empresa: Empresa
): ContaPagarReceber[] {
  const rand = mulberry32(seedFromCnpj(empresa.cnpj, 3));
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const lista: ContaPagarReceber[] = [];

  const fornecedoresPagar: Array<{
    descricao: string;
    contraparte: string;
    categoria: CategoriaConta;
    valor: [number, number];
  }> = [
    {
      descricao: "Fatura energia",
      contraparte: "CEEE Equatorial",
      categoria: "energia",
      valor: [400, 1_400],
    },
    {
      descricao: "Aluguel ponto comercial",
      contraparte: "Imobiliária Forte",
      categoria: "aluguel",
      valor: [3_500, 6_500],
    },
    {
      descricao: "Internet + telefonia",
      contraparte: "Vivo Empresas",
      categoria: "telefonia_internet",
      valor: [320, 690],
    },
    {
      descricao: "Compra de matéria-prima",
      contraparte: "Distribuidora União",
      categoria: "fornecedor",
      valor: [2_800, 9_400],
    },
    {
      descricao: "Anúncio Google Ads",
      contraparte: "Google Brasil",
      categoria: "marketing",
      valor: [600, 2_200],
    },
    {
      descricao: "Honorários contábeis",
      contraparte: "Contabilidade Andrade",
      categoria: "servicos",
      valor: [780, 1_200],
    },
    {
      descricao: "Reposição de estoque",
      contraparte: "Atacadão Plus",
      categoria: "fornecedor",
      valor: [1_500, 4_800],
    },
    {
      descricao: "DAS Simples Nacional",
      contraparte: "Receita Federal",
      categoria: "tributos",
      valor: [2_400, 5_800],
    },
  ];

  const recebimentos: Array<{
    descricao: string;
    contraparte: string;
    categoria: CategoriaConta;
    valor: [number, number];
  }> = [
    {
      descricao: "Venda parcelada",
      contraparte: "Cliente Ana Silva",
      categoria: "vendas",
      valor: [1_200, 4_800],
    },
    {
      descricao: "Boleto cliente",
      contraparte: "Restaurante Bom Gosto",
      categoria: "vendas",
      valor: [780, 3_500],
    },
    {
      descricao: "Serviço prestado",
      contraparte: "Loja Veredas",
      categoria: "servicos_prestados",
      valor: [1_800, 6_400],
    },
    {
      descricao: "Mensalidade contrato",
      contraparte: "Pizzaria do Bairro",
      categoria: "servicos_prestados",
      valor: [800, 1_400],
    },
  ];

  // contas a pagar — janela -10 até +60 dias
  for (let i = 0; i < fornecedoresPagar.length; i++) {
    const item = fornecedoresPagar[i]!;
    const offsetDias = -10 + Math.floor(rand() * 70);
    const venc = new Date(hoje.getTime() + offsetDias * DIA_MS);
    const valor = arredondar(
      item.valor[0] + rand() * (item.valor[1] - item.valor[0])
    );
    let status: StatusContaPagarReceber = "pendente";
    let pagoEm: string | undefined;
    if (offsetDias < -2) {
      // pode estar pago ou atrasado
      if (rand() < 0.7) {
        status = "pago";
        pagoEm = isoDia(
          new Date(venc.getTime() + Math.floor(rand() * 3) * DIA_MS)
        );
      } else {
        status = "atrasado";
      }
    } else if (offsetDias < 0) {
      status = rand() < 0.5 ? "atrasado" : "pago";
      if (status === "pago") {
        pagoEm = isoDia(new Date(venc.getTime() - DIA_MS));
      }
    }
    lista.push({
      id: `pagar-${empresa.id}-${i}-${pseudoUuid().slice(0, 6)}`,
      tipo: "pagar",
      descricao: item.descricao,
      contraparte: item.contraparte,
      valor,
      vencimento: isoDia(venc),
      categoria: item.categoria,
      status,
      pagoEm,
      criadoEm: new Date(venc.getTime() - 7 * DIA_MS).toISOString(),
    });
  }

  // contas a receber
  for (let i = 0; i < recebimentos.length * 2; i++) {
    const item = recebimentos[i % recebimentos.length]!;
    const offsetDias = -5 + Math.floor(rand() * 50);
    const venc = new Date(hoje.getTime() + offsetDias * DIA_MS);
    const valor = arredondar(
      item.valor[0] + rand() * (item.valor[1] - item.valor[0])
    );
    let status: StatusContaPagarReceber = "pendente";
    let pagoEm: string | undefined;
    if (offsetDias < -1) {
      if (rand() < 0.6) {
        status = "pago";
        pagoEm = isoDia(
          new Date(venc.getTime() + Math.floor(rand() * 2) * DIA_MS)
        );
      } else {
        status = "atrasado";
      }
    }
    lista.push({
      id: `receber-${empresa.id}-${i}-${pseudoUuid().slice(0, 6)}`,
      tipo: "receber",
      descricao: item.descricao,
      contraparte: item.contraparte,
      valor,
      vencimento: isoDia(venc),
      categoria: item.categoria,
      status,
      pagoEm,
      criadoEm: new Date(venc.getTime() - 14 * DIA_MS).toISOString(),
    });
  }

  return lista;
}

export interface ProjecaoEntrada {
  saldoHoje: number;
  contas: ContaPagarReceber[];
  transacoes: TransacaoBancaria[];
}

export function gerarFluxoCaixa(entrada: ProjecaoEntrada, dias = 90): FluxoCaixa {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  // 30 dias passados a partir das transações já existentes
  const passadoDias = 30;
  const totalDias = passadoDias + dias;

  // Mapear movimentos passados (transações reais)
  const movimentosPassados = new Map<string, { entradas: number; saidas: number }>();
  for (const tx of entrada.transacoes) {
    const dia = tx.data;
    const ref = movimentosPassados.get(dia) ?? { entradas: 0, saidas: 0 };
    if (tx.tipo === "credito") ref.entradas += tx.valor;
    else ref.saidas += tx.valor;
    movimentosPassados.set(dia, ref);
  }

  // Mapear movimentos futuros (contas a pagar/receber pendentes)
  const movimentosFuturos = new Map<string, { entradas: number; saidas: number }>();
  for (const conta of entrada.contas) {
    if (conta.status === "pago") continue;
    const dia = conta.vencimento;
    const ref = movimentosFuturos.get(dia) ?? { entradas: 0, saidas: 0 };
    if (conta.tipo === "receber") ref.entradas += conta.valor;
    else ref.saidas += conta.valor;
    movimentosFuturos.set(dia, ref);
  }

  // Reconstituir saldo dos últimos 30 dias andando para trás a partir do saldoHoje
  const pontos: FluxoCaixaPonto[] = [];

  const liquidoPassado = Array.from(movimentosPassados.entries())
    .filter(([dia]) => {
      const d = new Date(dia);
      const diff = (hoje.getTime() - d.getTime()) / DIA_MS;
      return diff >= 0 && diff <= passadoDias;
    })
    .reduce((acc, [, v]) => acc + v.entradas - v.saidas, 0);

  let saldoCorrente = entrada.saldoHoje - liquidoPassado;

  for (let i = -passadoDias; i <= dias; i++) {
    const data = new Date(hoje.getTime() + i * DIA_MS);
    const dia = isoDia(data);
    const passado = movimentosPassados.get(dia) ?? { entradas: 0, saidas: 0 };
    const futuro = movimentosFuturos.get(dia) ?? { entradas: 0, saidas: 0 };
    const entradas = i <= 0 ? passado.entradas : futuro.entradas;
    const saidas = i <= 0 ? passado.saidas : futuro.saidas;
    saldoCorrente = arredondar(saldoCorrente + entradas - saidas);
    pontos.push({
      data: dia,
      saldo: saldoCorrente,
      entradas: arredondar(entradas),
      saidas: arredondar(saidas),
      projecao: i > 0,
    });
  }

  function saldoEm(offset: number): number {
    const idx = passadoDias + offset;
    return pontos[idx]?.saldo ?? entrada.saldoHoje;
  }

  const diaNegativo = pontos
    .filter((p) => p.projecao && p.saldo < 0)
    .map((p) => p.data)[0] ?? null;

  return {
    saldoHoje: saldoEm(0),
    saldo30d: saldoEm(30),
    saldo60d: saldoEm(60),
    saldo90d: saldoEm(90),
    diaSaldoNegativo: diaNegativo,
    pontos,
  };
}

export type { RngState };
