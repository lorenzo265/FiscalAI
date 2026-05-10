import { calcularDAS } from "@/lib/fiscal/calcula-das";
import type { AnexoSimples } from "@/lib/schemas/empresa";

export type AtividadeSimulada =
  | "comercio"
  | "industria"
  | "servicos_anexo3"
  | "servicos_anexo5";

export interface EntradaSimulacao {
  faturamentoAnual: number;
  atividade: AtividadeSimulada;
  numeroFuncionarios: number;
}

export type RegimeSimulado = "SIMPLES" | "PRESUMIDO" | "REAL";

export interface CenarioSimulado {
  regime: RegimeSimulado;
  rotulo: string;
  impostoTotal: number;
  percentualSobreFaturamento: number;
  detalhamento: Array<{ tributo: string; valor: number }>;
  recomendacao: "vantajoso" | "neutro" | "evitar";
  observacao: string;
}

export interface ResultadoSimulacao {
  cenarios: CenarioSimulado[];
  vencedor: RegimeSimulado;
}

const FOLHA_MEDIA_POR_FUNCIONARIO = 4_500;

const ANEXO_POR_ATIVIDADE: Record<AtividadeSimulada, AnexoSimples> = {
  comercio: "I",
  industria: "II",
  servicos_anexo3: "III",
  servicos_anexo5: "V",
};

const PRESUMIDO_BASE = {
  comercio: 0.08,
  industria: 0.08,
  servicos_anexo3: 0.32,
  servicos_anexo5: 0.32,
};

export function simular(entrada: EntradaSimulacao): ResultadoSimulacao {
  const cenarios = [
    cenarioSimples(entrada),
    cenarioPresumido(entrada),
    cenarioReal(entrada),
  ];

  const vencedor = cenarios.reduce((min, c) =>
    c.impostoTotal < min.impostoTotal ? c : min
  );

  return {
    cenarios: cenarios.map((c) => ({
      ...c,
      recomendacao:
        c.regime === vencedor.regime
          ? "vantajoso"
          : c.impostoTotal <= vencedor.impostoTotal * 1.1
            ? "neutro"
            : "evitar",
    })),
    vencedor: vencedor.regime,
  };
}

function cenarioSimples(entrada: EntradaSimulacao): CenarioSimulado {
  const anexo = ANEXO_POR_ATIVIDADE[entrada.atividade];
  const receitaMes = entrada.faturamentoAnual / 12;
  const calc = calcularDAS({
    rbt12: entrada.faturamentoAnual,
    receitaMes,
    anexo,
  });
  const impostoAnual = calc.valorDAS * 12;
  const folhaAnual = entrada.numeroFuncionarios * FOLHA_MEDIA_POR_FUNCIONARIO * 13;

  return {
    regime: "SIMPLES",
    rotulo: `Simples Nacional · Anexo ${anexo}`,
    impostoTotal: Math.round(impostoAnual),
    percentualSobreFaturamento: impostoAnual / Math.max(1, entrada.faturamentoAnual),
    detalhamento: [
      { tributo: "DAS unificado", valor: Math.round(impostoAnual) },
    ],
    recomendacao: "neutro",
    observacao:
      entrada.atividade === "servicos_anexo5"
        ? `Anexo V — alíquotas mais altas. Folha anual estimada de R$ ${folhaAnual.toLocaleString("pt-BR")} pode te jogar pro Anexo III via Fator R.`
        : "Tudo unificado em uma única guia mensal.",
  };
}

function cenarioPresumido(entrada: EntradaSimulacao): CenarioSimulado {
  const baseIRPJ = entrada.faturamentoAnual * PRESUMIDO_BASE[entrada.atividade];
  const irpj = baseIRPJ * 0.15 + Math.max(0, baseIRPJ - 240_000) * 0.1;
  const csll = baseIRPJ * 0.09;
  const pis = entrada.faturamentoAnual * 0.0065;
  const cofins = entrada.faturamentoAnual * 0.03;
  const issOuIcms =
    entrada.atividade === "comercio" || entrada.atividade === "industria"
      ? entrada.faturamentoAnual * 0.18
      : entrada.faturamentoAnual * 0.05;
  const cppFolha = entrada.numeroFuncionarios * FOLHA_MEDIA_POR_FUNCIONARIO * 13 * 0.268;
  const total = irpj + csll + pis + cofins + issOuIcms + cppFolha;

  return {
    regime: "PRESUMIDO",
    rotulo: "Lucro Presumido",
    impostoTotal: Math.round(total),
    percentualSobreFaturamento: total / Math.max(1, entrada.faturamentoAnual),
    detalhamento: [
      { tributo: "IRPJ", valor: Math.round(irpj) },
      { tributo: "CSLL", valor: Math.round(csll) },
      { tributo: "PIS", valor: Math.round(pis) },
      { tributo: "Cofins", valor: Math.round(cofins) },
      {
        tributo:
          entrada.atividade === "comercio" || entrada.atividade === "industria"
            ? "ICMS"
            : "ISS",
        valor: Math.round(issOuIcms),
      },
      { tributo: "INSS patronal", valor: Math.round(cppFolha) },
    ],
    recomendacao: "neutro",
    observacao:
      "Apuração trimestral, declarações separadas. Costuma valer a pena com margem alta.",
  };
}

function cenarioReal(entrada: EntradaSimulacao): CenarioSimulado {
  const margemEstimada = 0.18;
  const lucro = entrada.faturamentoAnual * margemEstimada;
  const irpj = lucro * 0.15 + Math.max(0, lucro - 240_000) * 0.1;
  const csll = lucro * 0.09;
  const pis = entrada.faturamentoAnual * 0.0165;
  const cofins = entrada.faturamentoAnual * 0.076;
  const issOuIcms =
    entrada.atividade === "comercio" || entrada.atividade === "industria"
      ? entrada.faturamentoAnual * 0.18
      : entrada.faturamentoAnual * 0.05;
  const cppFolha = entrada.numeroFuncionarios * FOLHA_MEDIA_POR_FUNCIONARIO * 13 * 0.268;
  const total = irpj + csll + pis + cofins + issOuIcms + cppFolha;

  return {
    regime: "REAL",
    rotulo: "Lucro Real",
    impostoTotal: Math.round(total),
    percentualSobreFaturamento: total / Math.max(1, entrada.faturamentoAnual),
    detalhamento: [
      { tributo: "IRPJ", valor: Math.round(irpj) },
      { tributo: "CSLL", valor: Math.round(csll) },
      { tributo: "PIS não-cumulativo", valor: Math.round(pis) },
      { tributo: "Cofins não-cumulativo", valor: Math.round(cofins) },
      {
        tributo:
          entrada.atividade === "comercio" || entrada.atividade === "industria"
            ? "ICMS"
            : "ISS",
        valor: Math.round(issOuIcms),
      },
      { tributo: "INSS patronal", valor: Math.round(cppFolha) },
    ],
    recomendacao: "neutro",
    observacao:
      "Imposto sobre o lucro efetivo. Faz sentido se sua margem for baixa ou tiver muitos créditos.",
  };
}
