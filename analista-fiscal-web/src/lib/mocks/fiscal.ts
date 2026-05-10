import { calcularDAS, calcularProximoVencimentoDAS } from "@/lib/fiscal/calcula-das";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  ApuracaoFiscal,
  ComposicaoTributo,
  FiscalHealth,
  HistoricoMes,
} from "@/lib/schemas/fiscal";

export function gerarApuracaoMock(empresa: Empresa, hoje: Date = new Date()): ApuracaoFiscal {
  const ano = hoje.getMonth() === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();
  const mes = hoje.getMonth() === 0 ? 12 : hoje.getMonth();

  const fat12 = empresa.faturamento12m;
  const receitaMes = Math.round((fat12 / 12) * (0.92 + (mes % 5) * 0.04));
  const anexo = empresa.anexoSimples ?? "III";
  const calculo = calcularDAS({ rbt12: fat12, receitaMes, anexo });

  const fatorR = empresa.regime === "SIMPLES_NACIONAL" && (anexo === "III" || anexo === "V")
    ? {
        valor: 0.314,
        anexoAtual: anexo,
        atencao: false,
      }
    : undefined;

  const composicao = composicaoSimples(calculo.valorDAS, anexo);

  return {
    periodo: { ano, mes },
    faturamentoMes: receitaMes,
    faturamento12m: fat12,
    sublimiteEstadual: 3_600_000,
    tetoSimples: 4_800_000,
    fatorR,
    aliquotaEfetiva: calculo.aliquotaEfetiva,
    aliquotaNominal: calculo.aliquotaNominal,
    faixa: calculo.faixa,
    valorDAS: calculo.valorDAS,
    vencimento: calcularProximoVencimentoDAS(hoje).toISOString().slice(0, 10),
    status: "calculado",
    composicao,
    alertas: [],
  };
}

function composicaoSimples(total: number, anexo: string): ComposicaoTributo[] {
  const partes =
    anexo === "I"
      ? [
          { tributo: "ICMS", apelido: "ICMS — imposto estadual", percentual: 0.34 },
          { tributo: "CPP", apelido: "CPP — INSS patronal", percentual: 0.42 },
          { tributo: "PIS", apelido: "PIS sobre faturamento", percentual: 0.04 },
          { tributo: "COFINS", apelido: "Cofins sobre faturamento", percentual: 0.13 },
          { tributo: "IRPJ", apelido: "Imposto de renda PJ", percentual: 0.06 },
          { tributo: "CSLL", apelido: "Contribuição sobre lucro", percentual: 0.01 },
        ]
      : [
          { tributo: "ISS", apelido: "ISS — imposto municipal", percentual: 0.32 },
          { tributo: "CPP", apelido: "CPP — INSS patronal", percentual: 0.41 },
          { tributo: "PIS", apelido: "PIS sobre faturamento", percentual: 0.04 },
          { tributo: "COFINS", apelido: "Cofins sobre faturamento", percentual: 0.14 },
          { tributo: "IRPJ", apelido: "Imposto de renda PJ", percentual: 0.06 },
          { tributo: "CSLL", apelido: "Contribuição sobre lucro", percentual: 0.03 },
        ];

  return partes.map((p) => ({
    tributo: p.tributo,
    apelido: p.apelido,
    valor: total * p.percentual,
    percentual: p.percentual,
  }));
}

export function gerarFiscalHealthMock(empresa: Empresa, hoje: Date = new Date()): FiscalHealth {
  const apuracao = gerarApuracaoMock(empresa, hoje);
  const fatorRBaixo = (apuracao.fatorR?.valor ?? 1) < 0.32;

  const componentes: FiscalHealth["componentes"] = [
    {
      categoria: "obrigacoes_em_dia",
      label: "Obrigações em dia",
      pontuacao: 95,
      tom: "ok",
      mensagem: "Todas as guias dos últimos 6 meses foram pagas no prazo.",
    },
    {
      categoria: "certidoes_validas",
      label: "Certidões vigentes",
      pontuacao: 100,
      tom: "ok",
      mensagem: "CND Federal, CRF FGTS e CNDT estão dentro da validade.",
    },
    {
      categoria: "sem_intimacoes",
      label: "Sem intimações abertas",
      pontuacao: 100,
      tom: "ok",
      mensagem: "Nada pendente no e-CAC para sua empresa.",
    },
    {
      categoria: "fator_r_seguro",
      label: "Fator R seguro",
      pontuacao: fatorRBaixo ? 60 : 88,
      tom: fatorRBaixo ? "warn" : "ok",
      mensagem: fatorRBaixo
        ? "Sua folha está em 31% — pouco acima dos 28%. Tendência de queda nos próximos 3 meses pode mudar seu anexo."
        : "Folha em 31,4% — folga confortável acima dos 28% do limite.",
    },
    {
      categoria: "sublimite_seguro",
      label: "Sublimite estadual",
      pontuacao: 90,
      tom: "ok",
      mensagem: "Você está em 23% do sublimite de R$ 3,6 milhões.",
    },
    {
      categoria: "conciliacao_em_dia",
      label: "Conciliação bancária",
      pontuacao: 80,
      tom: "ok",
      mensagem: "12 transações pendentes de conciliação — nada urgente.",
    },
  ];

  const score = Math.round(
    componentes.reduce((acc, c) => acc + c.pontuacao, 0) / componentes.length
  );

  const tom: FiscalHealth["tom"] = score >= 80 ? "ok" : score >= 60 ? "warn" : "error";
  const titulo =
    tom === "ok"
      ? "Tudo em dia por aqui."
      : tom === "warn"
        ? "Atenção em alguns pontos."
        : "Ação urgente necessária.";

  const descricao =
    tom === "ok"
      ? "Sem nada pendente que precise da sua atenção agora."
      : tom === "warn"
        ? "Resolvendo o que está em amarelo, sua empresa volta ao verde."
        : "Há pendências que podem virar multa. Resolva antes do vencimento.";

  const alertasPrioritarios: FiscalHealth["alertasPrioritarios"] = [];
  if (fatorRBaixo) {
    alertasPrioritarios.push({
      id: "fator-r-tendencia",
      tom: "warn",
      titulo: "Folha de pagamento em queda",
      descricao:
        "Seu Fator R está em 31% e tem caído. Se ficar abaixo de 28%, sua alíquota dobra (vai pro Anexo V).",
      acao: { label: "Simular impacto", rota: "/fiscal/simulador" },
    });
  }

  alertasPrioritarios.push({
    id: "das-vencimento",
    tom: "info",
    titulo: `DAS de ${nomeMes(apuracao.periodo.mes)} disponível`,
    descricao: `Seu próximo pagamento vence em ${formatarVencimento(apuracao.vencimento)}.`,
    acao: { label: "Ver guia", rota: "/fiscal/guias" },
  });

  return {
    score,
    tom,
    titulo,
    descricao,
    componentes,
    alertasPrioritarios,
    proximaObrigacao: {
      titulo: "Entregar PGDAS-D",
      descricao:
        "Declaração mensal do Simples Nacional. Pode ser feita em 2 minutos pelo painel.",
      vencimento: apuracao.vencimento,
      acao: { label: "Preparar declaração", rota: "/fiscal" },
    },
  };
}

export function gerarHistoricoMock(empresa: Empresa, meses = 6): HistoricoMes[] {
  const fat12 = empresa.faturamento12m;
  const receitaBase = fat12 / 12;
  const anexo = empresa.anexoSimples ?? "III";
  const hoje = new Date();
  const out: HistoricoMes[] = [];
  for (let i = meses - 1; i >= 0; i--) {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    const variacao = 0.85 + ((i * 7 + d.getMonth()) % 30) / 100;
    const receita = Math.round(receitaBase * variacao);
    const calc = calcularDAS({ rbt12: fat12, receitaMes: receita, anexo });
    out.push({
      ano: d.getFullYear(),
      mes: d.getMonth() + 1,
      rotulo: nomeMesAbrev(d.getMonth() + 1),
      receita,
      imposto: Math.round(calc.valorDAS),
    });
  }
  return out;
}

function nomeMes(mes: number): string {
  const meses = [
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
  return meses[mes - 1] ?? "—";
}

function nomeMesAbrev(mes: number): string {
  const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  return meses[mes - 1] ?? "—";
}

function formatarVencimento(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}
