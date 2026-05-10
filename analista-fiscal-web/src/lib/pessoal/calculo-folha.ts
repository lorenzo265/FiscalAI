import type {
  EventoFolha,
  Funcionario,
  Holerite,
  StatusHolerite,
} from "@/lib/schemas/pessoal";

const SALARIO_MINIMO_2026 = 1_518;

interface FaixaProgressiva {
  ate: number;
  aliquota: number;
  deducao: number;
}

const FAIXAS_INSS_2026: FaixaProgressiva[] = [
  { ate: 1_518.0, aliquota: 0.075, deducao: 0 },
  { ate: 2_793.88, aliquota: 0.09, deducao: 22.77 },
  { ate: 4_190.83, aliquota: 0.12, deducao: 106.59 },
  { ate: 8_157.41, aliquota: 0.14, deducao: 190.4 },
];
const TETO_INSS_2026 = 951.62;

const FAIXAS_IRRF_2026: FaixaProgressiva[] = [
  { ate: 2_428.8, aliquota: 0, deducao: 0 },
  { ate: 2_826.65, aliquota: 0.075, deducao: 182.16 },
  { ate: 3_751.05, aliquota: 0.15, deducao: 394.16 },
  { ate: 4_664.68, aliquota: 0.225, deducao: 675.49 },
  { ate: Infinity, aliquota: 0.275, deducao: 908.73 },
];

const DEDUCAO_DEPENDENTE_IRRF = 189.59;
const ALIQUOTA_FGTS = 0.08;
const ALIQUOTA_INSS_PATRONAL = 0.2;
const ALIQUOTA_RAT = 0.02;
const ALIQUOTA_TERCEIROS = 0.058;

function arredondar(n: number): number {
  return Math.round(n * 100) / 100;
}

export function calcularInssEmpregado(base: number): number {
  if (base <= 0) return 0;
  for (const faixa of FAIXAS_INSS_2026) {
    if (base <= faixa.ate) {
      return arredondar(base * faixa.aliquota - faixa.deducao);
    }
  }
  return TETO_INSS_2026;
}

export function calcularIrrf(base: number, dependentes = 0): number {
  const baseAjustada = base - dependentes * DEDUCAO_DEPENDENTE_IRRF;
  if (baseAjustada <= 0) return 0;
  for (const faixa of FAIXAS_IRRF_2026) {
    if (baseAjustada <= faixa.ate) {
      const valor = baseAjustada * faixa.aliquota - faixa.deducao;
      return arredondar(Math.max(0, valor));
    }
  }
  return 0;
}

interface CalcularHoleriteInput {
  funcionario: Funcionario;
  ano: number;
  mes: number;
  diasTrabalhados?: number;
  dependentes?: number;
  status?: StatusHolerite;
  variaveis?: {
    horasExtras?: number;
    valeTransporteDesconto?: number;
    valeAlimentacaoDesconto?: number;
    faltas?: number;
  };
}

export function calcularHolerite({
  funcionario,
  ano,
  mes,
  diasTrabalhados = 30,
  dependentes = 0,
  status = "gerado",
  variaveis = {},
}: CalcularHoleriteInput): Holerite {
  const eventos: EventoFolha[] = [];

  const salario = funcionario.salario;
  const salarioProporcional = arredondar((salario * diasTrabalhados) / 30);

  if (funcionario.tipoContrato === "PJ") {
    eventos.push({
      codigo: "1001",
      descricao: "Honorários PJ",
      referencia: `${diasTrabalhados} dias`,
      tipo: "provento",
      valor: salarioProporcional,
    });
    const totalProventos = salarioProporcional;
    const totalDescontos = 0;
    return {
      id: idHolerite(funcionario.id, ano, mes),
      funcionarioId: funcionario.id,
      funcionarioNome: funcionario.nome,
      cargo: funcionario.cargo,
      ano,
      mes,
      competencia: chaveCompetencia(ano, mes),
      diasTrabalhados,
      salarioBase: salario,
      totalProventos: arredondar(totalProventos),
      totalDescontos: arredondar(totalDescontos),
      totalLiquido: arredondar(totalProventos - totalDescontos),
      baseInss: 0,
      baseFgts: 0,
      baseIrrf: 0,
      fgts: 0,
      inssEmpresa: 0,
      eventos,
      status,
      geradoEm: new Date().toISOString(),
    };
  }

  if (funcionario.tipoContrato === "ESTAGIO") {
    eventos.push({
      codigo: "1002",
      descricao: "Bolsa-auxílio estágio",
      referencia: `${diasTrabalhados} dias`,
      tipo: "provento",
      valor: salarioProporcional,
    });
    const totalProventos = salarioProporcional;
    return {
      id: idHolerite(funcionario.id, ano, mes),
      funcionarioId: funcionario.id,
      funcionarioNome: funcionario.nome,
      cargo: funcionario.cargo,
      ano,
      mes,
      competencia: chaveCompetencia(ano, mes),
      diasTrabalhados,
      salarioBase: salario,
      totalProventos: arredondar(totalProventos),
      totalDescontos: 0,
      totalLiquido: arredondar(totalProventos),
      baseInss: 0,
      baseFgts: 0,
      baseIrrf: 0,
      fgts: 0,
      inssEmpresa: 0,
      eventos,
      status,
      geradoEm: new Date().toISOString(),
    };
  }

  // CLT
  eventos.push({
    codigo: "0001",
    descricao: "Salário base",
    referencia: `${diasTrabalhados} dias`,
    tipo: "provento",
    valor: salarioProporcional,
  });

  let totalProventos = salarioProporcional;
  if (variaveis.horasExtras && variaveis.horasExtras > 0) {
    const valorHora = salario / 220;
    const valorHE = arredondar(valorHora * 1.5 * variaveis.horasExtras);
    eventos.push({
      codigo: "0050",
      descricao: "Horas extras 50%",
      referencia: `${variaveis.horasExtras}h`,
      tipo: "provento",
      valor: valorHE,
    });
    totalProventos += valorHE;
  }

  const baseInss = totalProventos;
  const inss = calcularInssEmpregado(baseInss);
  const baseIrrf = totalProventos - inss;
  const irrf = calcularIrrf(baseIrrf, dependentes);

  eventos.push({
    codigo: "9001",
    descricao: "INSS",
    referencia: percentualInss(baseInss),
    tipo: "desconto",
    valor: inss,
  });
  if (irrf > 0) {
    eventos.push({
      codigo: "9002",
      descricao: "IRRF",
      referencia: "tabela 2026",
      tipo: "desconto",
      valor: irrf,
    });
  }

  let totalDescontos = inss + irrf;
  if (variaveis.valeTransporteDesconto && variaveis.valeTransporteDesconto > 0) {
    eventos.push({
      codigo: "9100",
      descricao: "Vale-transporte (desconto)",
      referencia: "6%",
      tipo: "desconto",
      valor: variaveis.valeTransporteDesconto,
    });
    totalDescontos += variaveis.valeTransporteDesconto;
  }
  if (variaveis.valeAlimentacaoDesconto && variaveis.valeAlimentacaoDesconto > 0) {
    eventos.push({
      codigo: "9101",
      descricao: "Vale-alimentação (desconto)",
      referencia: "—",
      tipo: "desconto",
      valor: variaveis.valeAlimentacaoDesconto,
    });
    totalDescontos += variaveis.valeAlimentacaoDesconto;
  }

  const fgts = arredondar(baseInss * ALIQUOTA_FGTS);
  const inssEmpresa = arredondar(
    baseInss * (ALIQUOTA_INSS_PATRONAL + ALIQUOTA_RAT + ALIQUOTA_TERCEIROS)
  );

  return {
    id: idHolerite(funcionario.id, ano, mes),
    funcionarioId: funcionario.id,
    funcionarioNome: funcionario.nome,
    cargo: funcionario.cargo,
    ano,
    mes,
    competencia: chaveCompetencia(ano, mes),
    diasTrabalhados,
    salarioBase: salario,
    totalProventos: arredondar(totalProventos),
    totalDescontos: arredondar(totalDescontos),
    totalLiquido: arredondar(totalProventos - totalDescontos),
    baseInss: arredondar(baseInss),
    baseFgts: arredondar(baseInss),
    baseIrrf: arredondar(baseIrrf),
    fgts,
    inssEmpresa,
    eventos,
    status,
    geradoEm: new Date().toISOString(),
  };
}

function percentualInss(base: number): string {
  for (const faixa of FAIXAS_INSS_2026) {
    if (base <= faixa.ate) {
      return `${(faixa.aliquota * 100).toFixed(1).replace(".", ",")}%`;
    }
  }
  return "14,0%";
}

export function chaveCompetencia(ano: number, mes: number): string {
  return `${ano}-${String(mes).padStart(2, "0")}`;
}

export function idHolerite(funcionarioId: string, ano: number, mes: number): string {
  return `holerite-${funcionarioId}-${ano}-${String(mes).padStart(2, "0")}`;
}

export const PESSOAL_CONSTANTES = {
  SALARIO_MINIMO: SALARIO_MINIMO_2026,
  TETO_INSS: TETO_INSS_2026,
  ALIQUOTA_FGTS,
};
