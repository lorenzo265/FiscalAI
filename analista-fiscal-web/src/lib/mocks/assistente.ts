import { calcularDAS } from "@/lib/fiscal/calcula-das";
import { listarCertidoes, listarIntimacoes } from "@/lib/compliance/db-service";
import {
  listarContasBancarias,
  listarContasPagarReceber,
  listarTodasTransacoes,
} from "@/lib/controles/db-service";
import {
  listarFuncionarios,
  listarHolerites,
} from "@/lib/pessoal/db-service";
import { gerarFluxoCaixa } from "@/lib/mocks/controles";
import { formatarMoeda } from "@/lib/format/moeda";
import { formatarDataBR } from "@/lib/format/data";
import { pseudoUuid } from "@/lib/mocks/utils";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Bloco,
  Citacao,
  MensagemAssistente,
  Sugestao,
} from "@/lib/schemas/assistente";

const SUGESTOES_DEFAULT: Sugestao[] = [
  { texto: "Quanto pago de DAS?", pergunta: "Quanto pago de DAS este mês?" },
  { texto: "Como está o fluxo?", pergunta: "Como está meu fluxo de caixa?" },
  { texto: "Tem intimação aberta?", pergunta: "Tem alguma intimação aberta?" },
  { texto: "Vale virar fator R?", pergunta: "Vale a pena migrar pro fator R?" },
];

function novaResposta(parcial: Partial<MensagemAssistente>): MensagemAssistente {
  return {
    id: `msg-${pseudoUuid().slice(0, 10)}`,
    role: "assistant",
    texto: "",
    blocos: [],
    citacoes: [],
    sugestoes: [],
    criadoEm: new Date().toISOString(),
    ...parcial,
  };
}

export async function gerarResposta(
  pergunta: string,
  empresa: Empresa
): Promise<MensagemAssistente> {
  const p = pergunta.toLowerCase();

  if (/(das|simples|imposto|tribut)/.test(p)) {
    return responderDAS(empresa);
  }
  if (/(fluxo|caixa|saldo)/.test(p)) {
    return responderFluxo(empresa);
  }
  if (/(fator\s*r|anexo iii|anexo v)/.test(p)) {
    return responderFatorR(empresa);
  }
  if (/(certid|cnd|crf|cndt)/.test(p)) {
    return responderCertidoes();
  }
  if (/(intima|notifica|receita federal|e-cac)/.test(p)) {
    return responderIntimacoes();
  }
  if (/(folha|funcion|holerite|sal[aá]rio)/.test(p)) {
    return responderFolha();
  }
  if (/(banco|extrato|conciliar)/.test(p)) {
    return responderBancos();
  }
  if (/(receb|cliente|nota|fatura)/.test(p)) {
    return responderRecebiveis();
  }

  return responderDefault();
}

// =====================================================
// DAS
// =====================================================

async function responderDAS(empresa: Empresa): Promise<MensagemAssistente> {
  const fat12 = empresa.faturamento12m;
  const receitaMes = fat12 / 12;
  const anexo = empresa.anexoSimples ?? "III";
  const calculo = calcularDAS({
    rbt12: fat12,
    receitaMes,
    anexo,
  });
  const blocos: Bloco[] = [
    {
      tipo: "stat",
      rotulo: `DAS — competência atual (Anexo ${anexo})`,
      valor: formatarMoeda(calculo.valorDAS),
      tom: "info",
    },
    {
      tipo: "lista",
      titulo: "Como esse valor é calculado",
      itens: [
        {
          rotulo: "Receita do mês",
          valor: formatarMoeda(receitaMes),
        },
        {
          rotulo: "RBT12 (faturamento 12 meses)",
          valor: formatarMoeda(fat12),
        },
        {
          rotulo: "Alíquota efetiva",
          valor: `${(calculo.aliquotaEfetiva * 100).toFixed(2).replace(".", ",")}%`,
        },
      ],
    },
  ];

  const citacoes: Citacao[] = [
    {
      tipo: "apuracao",
      rotulo: `apuração ${rotuloPeriodoAtual()}`,
      rota: "/fiscal/apuracao",
    },
    {
      tipo: "guia",
      rotulo: "guia DAS",
      rota: "/fiscal/guias",
    },
  ];

  const texto = `O DAS dessa competência ficou em **${formatarMoeda(calculo.valorDAS)}**. A alíquota efetiva está em ${(calculo.aliquotaEfetiva * 100).toFixed(2).replace(".", ",")}% — alinhada ao porte e Anexo ${anexo}. Posso gerar a guia agora se quiser.`;

  return novaResposta({
    texto,
    blocos,
    citacoes,
    sugestoes: [
      { texto: "Gerar guia DAS", pergunta: "Quero gerar a guia do DAS." },
      { texto: "Comparar com fator R", pergunta: "Vale a pena migrar pro fator R?" },
      { texto: "Ver composição", pergunta: "Como é composto o DAS por imposto?" },
    ],
  });
}

// =====================================================
// Fluxo de caixa
// =====================================================

async function responderFluxo(_empresa: Empresa): Promise<MensagemAssistente> {
  const [contas, contasPR, transacoes] = await Promise.all([
    listarContasBancarias(),
    listarContasPagarReceber(),
    listarTodasTransacoes(),
  ]);
  const saldoHoje = contas.reduce((s, c) => s + c.saldo, 0);
  const fluxo = gerarFluxoCaixa(
    { saldoHoje, contas: contasPR, transacoes },
    90
  );

  const blocos: Bloco[] = [
    {
      tipo: "stat",
      rotulo: "Saldo hoje",
      valor: formatarMoeda(fluxo.saldoHoje),
      tom: fluxo.saldoHoje > 0 ? "ok" : "error",
    },
    {
      tipo: "lista",
      titulo: "Projeção 90 dias",
      itens: [
        {
          rotulo: "Em 30 dias",
          valor: formatarMoeda(fluxo.saldo30d),
        },
        {
          rotulo: "Em 60 dias",
          valor: formatarMoeda(fluxo.saldo60d),
        },
        {
          rotulo: "Em 90 dias",
          valor: formatarMoeda(fluxo.saldo90d),
        },
      ],
    },
  ];

  if (fluxo.diaSaldoNegativo) {
    blocos.push({
      tipo: "alerta",
      tom: "warn",
      titulo: `Caixa pode ficar negativo em ${formatarDataBR(fluxo.diaSaldoNegativo)}`,
      descricao:
        "Considere antecipar recebíveis ou renegociar a data dos boletos.",
    });
  } else {
    blocos.push({
      tipo: "alerta",
      tom: "ok",
      titulo: "Sem cruzamento abaixo de zero nos próximos 90 dias",
    });
  }

  const texto = `Você tem **${formatarMoeda(fluxo.saldoHoje)}** em caixa hoje. Projeção termina em **${formatarMoeda(fluxo.saldo90d)}** daqui a 90 dias.${
    fluxo.diaSaldoNegativo
      ? ` Atenção: o saldo cruza zero em ${formatarDataBR(fluxo.diaSaldoNegativo)}.`
      : " Sem alertas no horizonte."
  }`;

  return novaResposta({
    texto,
    blocos,
    citacoes: [
      { tipo: "extrato", rotulo: "fluxo de caixa", rota: "/controles" },
    ],
    sugestoes: [
      {
        texto: "Quem deve pra mim?",
        pergunta: "Quais clientes têm faturas pendentes?",
      },
      {
        texto: "Maiores despesas",
        pergunta: "Quais foram minhas maiores despesas no mês?",
      },
    ],
  });
}

// =====================================================
// Fator R
// =====================================================

async function responderFatorR(empresa: Empresa): Promise<MensagemAssistente> {
  const holerites = await listarHolerites();
  const ultimos12m = ultimas12Competencias();
  const folhaUltimos12m = holerites
    .filter((h) => ultimos12m.includes(h.competencia))
    .reduce((s, h) => s + h.totalProventos + h.fgts + h.inssEmpresa, 0);
  const fat12 = empresa.faturamento12m;
  const fatorR = fat12 > 0 ? folhaUltimos12m / fat12 : 0;
  const acima = fatorR >= 0.28;

  const blocos: Bloco[] = [
    {
      tipo: "stat",
      rotulo: "Fator R atual",
      valor: `${(fatorR * 100).toFixed(1).replace(".", ",")}%`,
      tom: acima ? "ok" : "warn",
    },
    {
      tipo: "lista",
      titulo: "Base do cálculo",
      itens: [
        { rotulo: "Folha (12 meses)", valor: formatarMoeda(folhaUltimos12m) },
        { rotulo: "Faturamento (12 meses)", valor: formatarMoeda(fat12) },
        { rotulo: "Limite legal", valor: "≥ 28%" },
      ],
    },
    {
      tipo: "alerta",
      tom: acima ? "ok" : "warn",
      titulo: acima
        ? "Empresa habilitada ao Anexo III via fator R"
        : "Fator R abaixo de 28% — Anexo V se aplica",
      descricao: acima
        ? "Mantém o Anexo III, alíquotas mais baixas em serviços."
        : "Aumentar a folha em pró-labore costuma ser a alavanca mais rápida.",
    },
  ];

  const texto = acima
    ? `Seu fator R está em **${(fatorR * 100).toFixed(1).replace(".", ",")}%** — acima dos 28%. Continua tributada pelo Anexo III, que é o mais leve em serviços.`
    : `Seu fator R está em **${(fatorR * 100).toFixed(1).replace(".", ",")}%** — abaixo dos 28%. Para reverter, precisa aumentar a folha em torno de ${formatarMoeda(0.28 * fat12 - folhaUltimos12m)} nos próximos 12 meses.`;

  return novaResposta({
    texto,
    blocos,
    citacoes: [
      { tipo: "folha", rotulo: "folha últimos 12 meses", rota: "/pessoal" },
      { tipo: "apuracao", rotulo: "histórico fiscal", rota: "/fiscal" },
    ],
    sugestoes: [
      {
        texto: "Simular com folha maior",
        pergunta: "Quanto pagaria de DAS se a folha fosse R$ 30 mil/mês?",
      },
      { texto: "Voltar pra DAS", pergunta: "Quanto pago de DAS este mês?" },
    ],
  });
}

// =====================================================
// Certidões
// =====================================================

async function responderCertidoes(): Promise<MensagemAssistente> {
  const certidoes = await listarCertidoes();
  if (certidoes.length === 0) {
    return novaResposta({
      texto: "Não encontrei nenhuma certidão registrada ainda.",
      sugestoes: SUGESTOES_DEFAULT,
    });
  }
  const vigentes = certidoes.filter((c) => c.status === "vigente").length;
  const proximas = certidoes
    .filter((c) => c.status === "vence_em_breve")
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));
  const vencidas = certidoes.filter((c) => c.status === "vencida");

  const blocos: Bloco[] = [
    {
      tipo: "stat",
      rotulo: "Certidões",
      valor: `${vigentes} de ${certidoes.length} vigentes`,
      tom: vencidas.length > 0 ? "error" : proximas.length > 0 ? "warn" : "ok",
    },
  ];
  if (proximas.length > 0) {
    blocos.push({
      tipo: "lista",
      titulo: "Vencem em breve",
      itens: proximas.map((c) => ({
        rotulo: c.numero,
        valor: formatarDataBR(c.vencimento),
      })),
    });
  }
  if (vencidas.length > 0) {
    blocos.push({
      tipo: "alerta",
      tom: "error",
      titulo: `${vencidas.length} certidão${vencidas.length > 1 ? "ões" : ""} vencida${vencidas.length > 1 ? "s" : ""}`,
      descricao:
        "Sem CND vigente você não consegue emitir NF-e nem participar de licitação.",
    });
  }

  const texto =
    vencidas.length > 0
      ? `Atenção: ${vencidas.length} certidão${vencidas.length > 1 ? "ões" : ""} vencida${vencidas.length > 1 ? "s" : ""}. Renove agora.`
      : proximas.length > 0
        ? `${vigentes} de ${certidoes.length} vigentes. ${proximas.length} vence${proximas.length > 1 ? "m" : ""} em menos de 30 dias.`
        : "Todas as certidões estão vigentes. Empresa em dia.";

  return novaResposta({
    texto,
    blocos,
    citacoes: [
      { tipo: "certidao", rotulo: "central de certidões", rota: "/compliance/certidoes" },
    ],
    sugestoes: [
      { texto: "Como renovar?", pergunta: "Como renovo uma certidão?" },
      { texto: "E intimações?", pergunta: "Tem alguma intimação aberta?" },
    ],
  });
}

// =====================================================
// Intimações
// =====================================================

async function responderIntimacoes(): Promise<MensagemAssistente> {
  const intimacoes = await listarIntimacoes();
  const abertas = intimacoes.filter(
    (i) => i.status !== "respondida" && i.status !== "encerrada"
  );
  if (abertas.length === 0) {
    return novaResposta({
      texto:
        "Nenhuma intimação aberta no momento. Sua caixa postal eletrônica está limpa.",
      blocos: [
        {
          tipo: "alerta",
          tom: "ok",
          titulo: "Sem pendências da Receita ou da Justiça",
        },
      ],
      citacoes: [
        { tipo: "intimacao", rotulo: "central de intimações", rota: "/compliance/intimacoes" },
      ],
      sugestoes: SUGESTOES_DEFAULT,
    });
  }

  const principal = abertas[0]!;
  const blocos: Bloco[] = [
    {
      tipo: "alerta",
      tom: "warn",
      titulo: `${abertas.length} intimação${abertas.length > 1 ? "ões" : ""} aberta${abertas.length > 1 ? "s" : ""}`,
      descricao: `Próximo prazo de resposta: ${formatarDataBR(principal.prazoResposta)}.`,
    },
    {
      tipo: "lista",
      titulo: "Intimações abertas",
      itens: abertas.map((i) => ({
        rotulo: `${i.assunto}`,
        valor: `prazo ${formatarDataBR(i.prazoResposta)}`,
      })),
    },
  ];
  return novaResposta({
    texto: `Você tem **${abertas.length}** intimação${abertas.length > 1 ? "ões" : ""} aberta${abertas.length > 1 ? "s" : ""}. A mais urgente é "${principal.assunto}", com prazo até ${formatarDataBR(principal.prazoResposta)}.`,
    blocos,
    citacoes: [
      { tipo: "intimacao", rotulo: "central de intimações", rota: "/compliance/intimacoes" },
    ],
    sugestoes: [
      {
        texto: "Encaminhar pro contador",
        pergunta: "Como envio essa intimação pro meu contador?",
      },
    ],
  });
}

// =====================================================
// Folha
// =====================================================

async function responderFolha(): Promise<MensagemAssistente> {
  const [funcionarios, holerites] = await Promise.all([
    listarFuncionarios(),
    listarHolerites(),
  ]);
  const ativos = funcionarios.filter((f) => f.status === "ativo").length;
  const competencia = competenciaAtual();
  const doMes = holerites.filter((h) => h.competencia === competencia);
  const totalBruto = doMes.reduce((s, h) => s + h.totalProventos, 0);
  const totalLiquido = doMes.reduce((s, h) => s + h.totalLiquido, 0);
  const fgts = doMes.reduce((s, h) => s + h.fgts, 0);

  return novaResposta({
    texto: `Você tem **${ativos}** funcionário${ativos === 1 ? "" : "s"} ativo${ativos === 1 ? "" : "s"}. A folha de ${competencia} está fechando em ${formatarMoeda(totalLiquido)} líquido (bruto ${formatarMoeda(totalBruto)}).`,
    blocos: [
      {
        tipo: "lista",
        titulo: `Folha ${competencia}`,
        itens: [
          { rotulo: "Bruto", valor: formatarMoeda(totalBruto) },
          { rotulo: "Líquido", valor: formatarMoeda(totalLiquido) },
          { rotulo: "FGTS", valor: formatarMoeda(fgts) },
          { rotulo: "Funcionários ativos", valor: String(ativos) },
        ],
      },
    ],
    citacoes: [
      { tipo: "folha", rotulo: "folha do mês", rota: `/pessoal/folha` },
    ],
    sugestoes: [
      {
        texto: "Gerar holerites",
        pergunta: "Como gero os holerites do mês?",
      },
      { texto: "E o eSocial?", pergunta: "O eSocial está em dia?" },
    ],
  });
}

// =====================================================
// Bancos / extratos
// =====================================================

async function responderBancos(): Promise<MensagemAssistente> {
  const contas = await listarContasBancarias();
  const transacoes = await listarTodasTransacoes();
  const naoConciliadas = transacoes.filter((t) => !t.conciliada).length;
  const total = transacoes.length;

  return novaResposta({
    texto: `Você tem **${contas.length}** conta${contas.length === 1 ? "" : "s"} conectada${contas.length === 1 ? "" : "s"}. Saldo total: ${formatarMoeda(contas.reduce((s, c) => s + c.saldo, 0))}.`,
    blocos: [
      {
        tipo: "stat",
        rotulo: "Transações pendentes de conciliação",
        valor: `${naoConciliadas} de ${total}`,
        tom: naoConciliadas > 30 ? "warn" : "ok",
      },
      {
        tipo: "lista",
        titulo: "Contas",
        itens: contas.map((c) => ({
          rotulo: c.apelido,
          valor: formatarMoeda(c.saldo),
        })),
      },
    ],
    citacoes: [
      { tipo: "extrato", rotulo: "bancos conectados", rota: "/controles/bancos" },
    ],
    sugestoes: [
      {
        texto: "Conciliar agora",
        pergunta: "Como concilio as transações pendentes?",
      },
    ],
  });
}

// =====================================================
// Recebíveis
// =====================================================

async function responderRecebiveis(): Promise<MensagemAssistente> {
  const contas = await listarContasPagarReceber();
  const receberAbertas = contas.filter(
    (c) => c.tipo === "receber" && c.status !== "pago"
  );
  const total = receberAbertas.reduce((s, c) => s + c.valor, 0);
  const atrasadas = receberAbertas.filter((c) => c.status === "atrasado");

  return novaResposta({
    texto: `Tem **${formatarMoeda(total)}** em contas a receber abertas. ${atrasadas.length > 0 ? `Atenção: ${atrasadas.length} já estão atrasadas.` : "Todas dentro do prazo até agora."}`,
    blocos: [
      {
        tipo: "stat",
        rotulo: "Total a receber",
        valor: formatarMoeda(total),
        tom: atrasadas.length > 0 ? "warn" : "ok",
      },
      {
        tipo: "lista",
        titulo: "Próximos vencimentos",
        itens: receberAbertas
          .slice(0, 5)
          .map((c) => ({
            rotulo: `${c.descricao} · ${c.contraparte}`,
            valor: formatarDataBR(c.vencimento),
          })),
      },
    ],
    citacoes: [
      { tipo: "lancamento", rotulo: "contas a receber", rota: "/controles/receber" },
    ],
    sugestoes: [
      {
        texto: "Quem está atrasado?",
        pergunta: "Quais clientes estão com pagamento atrasado?",
      },
    ],
  });
}

// =====================================================
// Default
// =====================================================

function responderDefault(): MensagemAssistente {
  return novaResposta({
    texto:
      "Posso responder sobre tributos, fluxo de caixa, fator R, certidões, folha de pagamento e mais. Tente uma das sugestões abaixo ou pergunte direto.",
    blocos: [
      {
        tipo: "lista",
        titulo: "O que sei fazer",
        itens: [
          { rotulo: "Apuração e simulação de tributos" },
          { rotulo: "Projeção de fluxo de caixa 90 dias" },
          { rotulo: "Análise de fator R e regime tributário" },
          { rotulo: "Acompanhamento de certidões e intimações" },
          { rotulo: "Resumo de folha e eSocial" },
        ],
      },
    ],
    sugestoes: SUGESTOES_DEFAULT,
  });
}

export function mensagemSaudacao(empresa: Empresa): MensagemAssistente {
  const primeiroNome = empresa.razaoSocial.split(/\s+/)[0] ?? "";
  return novaResposta({
    role: "assistant",
    texto: `Olá! Sou seu analista fiscal. Posso responder sobre tributos, fluxo de caixa, certidões, folha — qualquer coisa do dia-a-dia da ${primeiroNome}.`,
    sugestoes: SUGESTOES_DEFAULT,
  });
}

// =====================================================
// Helpers
// =====================================================

function competenciaAtual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function ultimas12Competencias(): string[] {
  const lista: string[] = [];
  const d = new Date();
  for (let i = 0; i < 12; i++) {
    const ref = new Date(d.getFullYear(), d.getMonth() - i, 1);
    lista.push(
      `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}`
    );
  }
  return lista;
}

const NOMES_MES_COMPLETO = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

function rotuloPeriodoAtual(): string {
  const d = new Date();
  return `${NOMES_MES_COMPLETO[d.getMonth()]}/${d.getFullYear()}`;
}
