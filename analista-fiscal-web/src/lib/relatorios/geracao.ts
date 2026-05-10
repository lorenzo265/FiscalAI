import { buscarConta, PLANO_CONTAS } from "@/lib/mocks/seeds/plano-contas";
import { montarBalancete } from "@/lib/contabil/motor";
import type { LancamentoContabil } from "@/lib/schemas/contabil";
import type { ContaPagarReceber } from "@/lib/schemas/controles";
import type { Holerite } from "@/lib/schemas/pessoal";
import type {
  BalancoPatrimonial,
  DFC,
  DreComparativo,
  Indicador,
  LinhaBalanco,
  LinhaDfc,
  LinhaDre,
  PeriodoRelatorio,
  SparkPoint,
} from "@/lib/schemas/relatorios";

// =====================================================
// Helpers
// =====================================================

const NOMES_MES_CURTO = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

function periodoLabel(ano: number, mes: number): string {
  return `${NOMES_MES_CURTO[mes - 1]}/${String(ano).slice(-2)}`;
}

function noPeriodo(data: string, ano: number, mes: number): boolean {
  const m = `${ano}-${String(mes).padStart(2, "0")}`;
  return data.startsWith(m);
}

function ateOFimDoPeriodo(data: string, ano: number, mes: number): boolean {
  const limite = `${ano}-${String(mes).padStart(2, "0")}-31`;
  return data <= limite;
}

function arredondar(n: number): number {
  return Math.round(n * 100) / 100;
}

interface ValoresPeriodo {
  receitaServicos: number;
  receitaVendas: number;
  deducoes: number;
  custoMercadorias: number;
  pessoal: number;
  alugueis: number;
  servicosTerceiros: number;
  materiais: number;
  outrasDespesasOp: number;
  receitaFinanceira: number;
  despesaFinanceira: number;
}

function valoresDoPeriodo(
  lancamentos: LancamentoContabil[],
  ano: number,
  mes: number
): ValoresPeriodo {
  const v: ValoresPeriodo = {
    receitaServicos: 0,
    receitaVendas: 0,
    deducoes: 0,
    custoMercadorias: 0,
    pessoal: 0,
    alugueis: 0,
    servicosTerceiros: 0,
    materiais: 0,
    outrasDespesasOp: 0,
    receitaFinanceira: 0,
    despesaFinanceira: 0,
  };
  for (const l of lancamentos) {
    if (!noPeriodo(l.data, ano, mes)) continue;
    const cD = buscarConta(l.contaDebito);
    const cC = buscarConta(l.contaCredito);

    if (cC?.codigo === "4.1.1") v.receitaServicos += l.valor;
    if (cC?.codigo === "4.1.2") v.receitaVendas += l.valor;
    if (cC?.codigo === "4.2") v.receitaFinanceira += l.valor;

    if (cD?.codigo === "5.1.1") v.pessoal += l.valor;
    if (cD?.codigo === "5.1.2") v.alugueis += l.valor;
    if (cD?.codigo === "5.1.3") v.servicosTerceiros += l.valor;
    if (cD?.codigo === "5.1.4") v.materiais += l.valor;
    if (cD?.codigo === "5.1.5") v.deducoes += l.valor;
    if (cD?.codigo === "5.2.1") v.despesaFinanceira += l.valor;

    // Custo de mercadorias = saída de estoque (se houver). Mock simplificado:
    // 35% das deduções do mês como referência de CMV.
  }
  // CMV simplificado para empresa Simples: ~25% da receita de vendas
  v.custoMercadorias = arredondar(v.receitaVendas * 0.25);
  return v;
}

// =====================================================
// DRE
// =====================================================

export function gerarDreComparativo(
  lancamentos: LancamentoContabil[],
  hoje: Date = new Date()
): DreComparativo {
  const periodos: PeriodoRelatorio[] = [
    { ano: hoje.getFullYear(), mes: hoje.getMonth() + 1, rotulo: "Mês atual" },
  ];
  const refAnt = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  periodos.push({
    ano: refAnt.getFullYear(),
    mes: refAnt.getMonth() + 1,
    rotulo: "Mês anterior",
  });
  periodos.push({
    ano: hoje.getFullYear() - 1,
    mes: hoje.getMonth() + 1,
    rotulo: `${NOMES_MES_CURTO[hoje.getMonth()]}/${String(hoje.getFullYear() - 1).slice(-2)}`,
  });

  const valores = periodos.map((p) =>
    valoresDoPeriodo(lancamentos, p.ano, p.mes)
  );

  const linhas: LinhaDre[] = [];

  function linhaSecao(rotulo: string) {
    linhas.push({
      chave: `secao-${rotulo}`,
      rotulo,
      tipo: "secao",
      valores: [0, 0, 0],
      formato: "moeda",
    });
  }

  function linhaValor(
    chave: string,
    rotulo: string,
    pegar: (v: ValoresPeriodo) => number,
    tipo: LinhaDre["tipo"] = "linha"
  ) {
    linhas.push({
      chave,
      rotulo,
      tipo,
      valores: valores.map((v) => arredondar(pegar(v))),
      formato: "moeda",
    });
  }

  function calcular(
    chave: string,
    rotulo: string,
    fn: (v: ValoresPeriodo) => number,
    tipo: LinhaDre["tipo"] = "subtotal"
  ) {
    linhas.push({
      chave,
      rotulo,
      tipo,
      valores: valores.map((v) => arredondar(fn(v))),
      formato: "moeda",
    });
  }

  linhaSecao("Receita");
  linhaValor("rec-serv", "Receita de serviços", (v) => v.receitaServicos);
  linhaValor("rec-vendas", "Receita de vendas", (v) => v.receitaVendas);
  calcular(
    "receita-bruta",
    "Receita bruta",
    (v) => v.receitaServicos + v.receitaVendas,
    "subtotal"
  );

  linhaSecao("Deduções");
  linhaValor(
    "ded-tributos",
    "Tributos sobre a receita (DAS, ISS)",
    (v) => -v.deducoes,
    "deducao"
  );
  calcular(
    "receita-liquida",
    "Receita líquida",
    (v) => v.receitaServicos + v.receitaVendas - v.deducoes,
    "subtotal"
  );

  linhaSecao("Custo");
  linhaValor("cmv", "Custo de mercadorias / serviços", (v) => -v.custoMercadorias, "deducao");
  calcular(
    "lucro-bruto",
    "Lucro bruto",
    (v) =>
      v.receitaServicos +
      v.receitaVendas -
      v.deducoes -
      v.custoMercadorias,
    "subtotal"
  );

  linhaSecao("Despesas operacionais");
  linhaValor("desp-pessoal", "Pessoal e encargos", (v) => -v.pessoal, "deducao");
  linhaValor("desp-aluguel", "Aluguel e condomínio", (v) => -v.alugueis, "deducao");
  linhaValor("desp-servicos", "Serviços de terceiros", (v) => -v.servicosTerceiros, "deducao");
  linhaValor("desp-materiais", "Materiais e insumos", (v) => -v.materiais, "deducao");

  calcular(
    "resultado-operacional",
    "Resultado operacional",
    (v) =>
      v.receitaServicos +
      v.receitaVendas -
      v.deducoes -
      v.custoMercadorias -
      v.pessoal -
      v.alugueis -
      v.servicosTerceiros -
      v.materiais,
    "subtotal"
  );

  linhaSecao("Resultado financeiro");
  linhaValor("rec-fin", "Receitas financeiras", (v) => v.receitaFinanceira);
  linhaValor("desp-fin", "Despesas financeiras", (v) => -v.despesaFinanceira, "deducao");

  calcular(
    "lucro-liquido",
    "Lucro líquido do período",
    (v) =>
      v.receitaServicos +
      v.receitaVendas -
      v.deducoes -
      v.custoMercadorias -
      v.pessoal -
      v.alugueis -
      v.servicosTerceiros -
      v.materiais +
      v.receitaFinanceira -
      v.despesaFinanceira,
    "total"
  );

  // Margens
  function margem(numerador: (v: ValoresPeriodo) => number) {
    return valores.map((v) => {
      const receita = v.receitaServicos + v.receitaVendas;
      if (receita <= 0) return 0;
      return arredondar((numerador(v) / receita) * 100) / 100;
    });
  }

  linhas.push({
    chave: "margem-bruta",
    rotulo: "Margem bruta",
    tipo: "margem",
    formato: "percentual",
    valores: margem(
      (v) =>
        v.receitaServicos +
        v.receitaVendas -
        v.deducoes -
        v.custoMercadorias
    ),
  });
  linhas.push({
    chave: "margem-operacional",
    rotulo: "Margem operacional",
    tipo: "margem",
    formato: "percentual",
    valores: margem(
      (v) =>
        v.receitaServicos +
        v.receitaVendas -
        v.deducoes -
        v.custoMercadorias -
        v.pessoal -
        v.alugueis -
        v.servicosTerceiros -
        v.materiais
    ),
  });
  linhas.push({
    chave: "margem-liquida",
    rotulo: "Margem líquida",
    tipo: "margem",
    formato: "percentual",
    valores: margem(
      (v) =>
        v.receitaServicos +
        v.receitaVendas -
        v.deducoes -
        v.custoMercadorias -
        v.pessoal -
        v.alugueis -
        v.servicosTerceiros -
        v.materiais +
        v.receitaFinanceira -
        v.despesaFinanceira
    ),
  });

  return { periodos, linhas };
}

// =====================================================
// Balanço Patrimonial
// =====================================================

export function gerarBalanco(
  lancamentos: LancamentoContabil[],
  hoje: Date = new Date()
): BalancoPatrimonial {
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth() + 1;
  const competencia = `${ano}-${String(mes).padStart(2, "0")}`;

  // Acumulado até o fim do mês
  const acumulados = lancamentos.filter((l) =>
    ateOFimDoPeriodo(l.data, ano, mes)
  );
  const { raizes } = montarBalancete(acumulados);

  const ativo: LinhaBalanco[] = [];
  const passivoEPl: LinhaBalanco[] = [];

  function visitar(linha: typeof raizes[number], destino: "ativo" | "passivo_pl") {
    const conta = linha.conta;
    const isResultado =
      conta.natureza === "receita" || conta.natureza === "despesa";
    if (isResultado) return;

    const destaque: LinhaBalanco["destaque"] =
      conta.nivel === 1 ? "grupo" : conta.nivel === 2 ? "subgrupo" : "conta";

    // Para conta analítica, só inclui se tiver saldo
    if (conta.analitica && Math.abs(linha.saldoAtual) < 0.01) return;
    // Para sintética com saldo zero, esconde também
    if (!conta.analitica && Math.abs(linha.saldoAtual) < 0.01 && linha.filhos.length === 0) {
      return;
    }

    const linhaOut: LinhaBalanco = {
      codigo: conta.codigo,
      rotulo: conta.nome,
      valor: arredondar(linha.saldoAtual),
      destaque,
      nivel: conta.nivel,
    };

    if (destino === "ativo") ativo.push(linhaOut);
    else passivoEPl.push(linhaOut);

    for (const f of linha.filhos) visitar(f, destino);
  }

  for (const r of raizes) {
    if (r.conta.natureza === "ativo") visitar(r, "ativo");
    if (
      r.conta.natureza === "passivo" ||
      r.conta.natureza === "patrimonio_liquido"
    ) {
      visitar(r, "passivo_pl");
    }
  }

  // Calcular resultado do exercício acumulado e injetar no PL
  let receitaAcum = 0;
  let despesaAcum = 0;
  for (const l of acumulados) {
    const cC = buscarConta(l.contaCredito);
    const cD = buscarConta(l.contaDebito);
    if (cC?.natureza === "receita") receitaAcum += l.valor;
    if (cD?.natureza === "despesa") despesaAcum += l.valor;
  }
  const resultadoExercicio = arredondar(receitaAcum - despesaAcum);

  if (Math.abs(resultadoExercicio) > 0.01) {
    // Injeta como linha de PL após "Resultado do Exercício"
    const idxResultado = passivoEPl.findIndex(
      (l) => l.codigo === "3.2"
    );
    if (idxResultado >= 0) {
      passivoEPl.splice(idxResultado + 1, 0, {
        codigo: "3.2.99",
        rotulo: "Lucro do exercício (período corrente)",
        valor: resultadoExercicio,
        destaque: "conta",
        nivel: 3,
      });
    } else {
      passivoEPl.push({
        codigo: "3.2.99",
        rotulo: "Lucro do exercício (período corrente)",
        valor: resultadoExercicio,
        destaque: "conta",
        nivel: 3,
      });
    }
  }

  const totalAtivo = ativo
    .filter((l) => l.destaque === "grupo")
    .reduce((s, l) => s + l.valor, 0);
  const totalPassivo = passivoEPl
    .filter((l) => l.destaque === "grupo" && l.codigo === "2")
    .reduce((s, l) => s + l.valor, 0);
  const totalPlBase = passivoEPl
    .filter((l) => l.destaque === "grupo" && l.codigo === "3")
    .reduce((s, l) => s + l.valor, 0);
  const totalPl = arredondar(totalPlBase + resultadoExercicio);

  const totalPassivoPl = arredondar(totalPassivo + totalPl);
  const diferenca = arredondar(totalAtivo - totalPassivoPl);
  const bate = Math.abs(diferenca) < 1;

  return {
    competencia,
    ativo,
    passivoEPl,
    totalAtivo: arredondar(totalAtivo),
    totalPassivo: arredondar(totalPassivo),
    totalPl,
    bate,
    diferenca,
  };
}

// =====================================================
// DFC (método indireto, simplificado)
// =====================================================

export function gerarDFC(
  lancamentos: LancamentoContabil[],
  hoje: Date = new Date()
): DFC {
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth() + 1;
  const competencia = `${ano}-${String(mes).padStart(2, "0")}`;
  const v = valoresDoPeriodo(lancamentos, ano, mes);

  const lucroLiquido =
    v.receitaServicos +
    v.receitaVendas -
    v.deducoes -
    v.custoMercadorias -
    v.pessoal -
    v.alugueis -
    v.servicosTerceiros -
    v.materiais +
    v.receitaFinanceira -
    v.despesaFinanceira;

  // Saldo bancário inicial e final no mês
  const inicioMes = `${ano}-${String(mes).padStart(2, "0")}-01`;
  const fimMes = `${ano}-${String(mes).padStart(2, "0")}-31`;
  let saldoInicial = 0;
  let saldoFinal = 0;
  for (const l of lancamentos) {
    if (l.contaDebito === "1.1.1.02" || l.contaCredito === "1.1.1.02") {
      const sinal = l.contaDebito === "1.1.1.02" ? 1 : -1;
      if (l.data < inicioMes) saldoInicial += l.valor * sinal;
      if (l.data <= fimMes) saldoFinal += l.valor * sinal;
    }
  }
  saldoInicial = arredondar(saldoInicial);
  saldoFinal = arredondar(saldoFinal);

  // Variação de capital de giro (simplificada)
  const varCapitalGiro = arredondar(saldoFinal - saldoInicial - lucroLiquido);

  const linhas: LinhaDfc[] = [];

  linhas.push({
    chave: "secao-op",
    rotulo: "Atividades Operacionais",
    tipo: "secao",
    valor: 0,
  });
  linhas.push({
    chave: "ll",
    rotulo: "Lucro líquido do período",
    tipo: "linha",
    valor: arredondar(lucroLiquido),
  });
  linhas.push({
    chave: "ajuste-cmv",
    rotulo: "(+) Custo dos produtos vendidos (não-caixa)",
    tipo: "linha",
    valor: arredondar(v.custoMercadorias * 0.4),
  });
  linhas.push({
    chave: "var-clientes",
    rotulo: "(±) Variação em contas a receber",
    tipo: "linha",
    valor: arredondar(varCapitalGiro * 0.5),
  });
  linhas.push({
    chave: "var-fornecedores",
    rotulo: "(±) Variação em fornecedores",
    tipo: "linha",
    valor: arredondar(varCapitalGiro * 0.3),
  });

  const totalOp = arredondar(
    lucroLiquido +
      v.custoMercadorias * 0.4 +
      varCapitalGiro * 0.5 +
      varCapitalGiro * 0.3
  );
  linhas.push({
    chave: "total-op",
    rotulo: "Caixa gerado pelas operações",
    tipo: "subtotal",
    valor: totalOp,
  });

  linhas.push({
    chave: "secao-inv",
    rotulo: "Atividades de Investimento",
    tipo: "secao",
    valor: 0,
  });
  // Mock simples — sem investimentos no mês corrente
  linhas.push({
    chave: "inv-imob",
    rotulo: "Aquisição de imobilizado",
    tipo: "linha",
    valor: 0,
  });
  linhas.push({
    chave: "total-inv",
    rotulo: "Caixa em investimentos",
    tipo: "subtotal",
    valor: 0,
  });

  linhas.push({
    chave: "secao-fin",
    rotulo: "Atividades de Financiamento",
    tipo: "secao",
    valor: 0,
  });
  linhas.push({
    chave: "fin-emprestimo",
    rotulo: "Captação / amortização de empréstimos",
    tipo: "linha",
    valor: 0,
  });
  linhas.push({
    chave: "fin-distribuicao",
    rotulo: "Distribuição de lucros",
    tipo: "linha",
    valor: 0,
  });
  linhas.push({
    chave: "total-fin",
    rotulo: "Caixa em financiamento",
    tipo: "subtotal",
    valor: 0,
  });

  linhas.push({
    chave: "variacao-caixa",
    rotulo: "Variação líquida de caixa",
    tipo: "total",
    valor: arredondar(saldoFinal - saldoInicial),
  });

  return {
    competencia,
    saldoInicial,
    saldoFinal,
    linhas,
  };
}

// =====================================================
// Indicadores
// =====================================================

interface IndicadoresInput {
  lancamentos: LancamentoContabil[];
  contasPagarReceber: ContaPagarReceber[];
  holerites: Holerite[];
  hoje?: Date;
}

export function gerarIndicadores({
  lancamentos,
  contasPagarReceber,
  holerites,
  hoje = new Date(),
}: IndicadoresInput): Indicador[] {
  // Série de 12 meses para sparklines
  const meses: { ano: number; mes: number; rotulo: string }[] = [];
  for (let i = 11; i >= 0; i--) {
    const ref = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    meses.push({
      ano: ref.getFullYear(),
      mes: ref.getMonth() + 1,
      rotulo: periodoLabel(ref.getFullYear(), ref.getMonth() + 1),
    });
  }

  function spark(fn: (vals: ValoresPeriodo) => number): SparkPoint[] {
    return meses.map((m) => ({
      rotulo: m.rotulo,
      valor: arredondar(fn(valoresDoPeriodo(lancamentos, m.ano, m.mes))),
    }));
  }

  function variacao(serie: SparkPoint[]): { variacao: number; direcao: Indicador["direcao"] } {
    if (serie.length < 2) return { variacao: 0, direcao: "estavel" };
    const ultimo = serie[serie.length - 1]!.valor;
    const anterior = serie[serie.length - 2]!.valor;
    if (Math.abs(anterior) < 0.01) return { variacao: 0, direcao: "estavel" };
    const v = ((ultimo - anterior) / Math.abs(anterior)) * 100;
    const direcao: Indicador["direcao"] =
      Math.abs(v) < 1 ? "estavel" : v >= 0 ? "alta" : "queda";
    return { variacao: arredondar(v), direcao };
  }

  // Receita líquida
  const sparkReceitaLiquida = spark(
    (v) => v.receitaServicos + v.receitaVendas - v.deducoes
  );
  // Lucro líquido
  const sparkLucroLiquido = spark(
    (v) =>
      v.receitaServicos +
      v.receitaVendas -
      v.deducoes -
      v.custoMercadorias -
      v.pessoal -
      v.alugueis -
      v.servicosTerceiros -
      v.materiais +
      v.receitaFinanceira -
      v.despesaFinanceira
  );

  // Margem líquida
  const sparkMargemLiquida = sparkReceitaLiquida.map((p, i) => {
    const ll = sparkLucroLiquido[i]!.valor;
    const rl = p.valor;
    return {
      rotulo: p.rotulo,
      valor: rl > 0 ? arredondar((ll / rl) * 100) : 0,
    };
  });

  const balanco = gerarBalanco(lancamentos, hoje);

  // Liquidez corrente = AC / PC
  const ativoCirculante =
    balanco.ativo.find((l) => l.codigo === "1.1")?.valor ??
    balanco.totalAtivo;
  const passivoCirculante =
    balanco.passivoEPl.find((l) => l.codigo === "2.1")?.valor ??
    balanco.totalPassivo;
  const liquidezCorrente =
    passivoCirculante > 0 ? ativoCirculante / passivoCirculante : 0;

  // Endividamento = passivo / (passivo + PL)
  const endividamento =
    balanco.totalPassivo + balanco.totalPl > 0
      ? (balanco.totalPassivo / (balanco.totalPassivo + balanco.totalPl)) * 100
      : 0;

  // Ticket médio: receita / qtd notas no mês corrente
  const valoresAtual = valoresDoPeriodo(
    lancamentos,
    hoje.getFullYear(),
    hoje.getMonth() + 1
  );
  const receitaAtual =
    valoresAtual.receitaServicos + valoresAtual.receitaVendas;
  const lancamentosVenda = lancamentos.filter(
    (l) =>
      noPeriodo(l.data, hoje.getFullYear(), hoje.getMonth() + 1) &&
      (l.contaCredito === "4.1.1" || l.contaCredito === "4.1.2")
  );
  const ticketMedio =
    lancamentosVenda.length > 0
      ? receitaAtual / lancamentosVenda.length
      : 0;

  // PMR — média de dias entre vencimento de contas a receber pendentes/atrasadas
  const hojeMs = hoje.getTime();
  const recebiveis = contasPagarReceber.filter(
    (c) => c.tipo === "receber" && c.status !== "pago"
  );
  const pmr =
    recebiveis.length > 0
      ? recebiveis.reduce((s, c) => {
          const dias = (new Date(c.vencimento).getTime() - hojeMs) / (24 * 3600 * 1000);
          return s + Math.max(0, dias);
        }, 0) / recebiveis.length
      : 0;

  // ROI ≈ lucro líquido acumulado 12m / ativo total
  const lucroAcumulado12m = sparkLucroLiquido.reduce(
    (s, p) => s + p.valor,
    0
  );
  const roi =
    balanco.totalAtivo > 0
      ? (lucroAcumulado12m / balanco.totalAtivo) * 100
      : 0;

  // ROE = lucro / PL
  const roe = balanco.totalPl > 0 ? (lucroAcumulado12m / balanco.totalPl) * 100 : 0;

  // Custo da folha
  const sparkFolha = sparkReceitaLiquida.map((p, i) => {
    const ref = meses[i]!;
    const total = holerites
      .filter((h) => h.ano === ref.ano && h.mes === ref.mes)
      .reduce((s, h) => s + h.totalProventos + h.fgts + h.inssEmpresa, 0);
    return { rotulo: p.rotulo, valor: arredondar(total) };
  });

  function tomLiquidez(v: number): Indicador["tom"] {
    if (v >= 1.5) return "ok";
    if (v >= 1) return "warn";
    return "error";
  }
  function tomEndividamento(v: number): Indicador["tom"] {
    if (v <= 40) return "ok";
    if (v <= 65) return "warn";
    return "error";
  }
  function tomMargem(v: number): Indicador["tom"] {
    if (v >= 15) return "ok";
    if (v >= 5) return "warn";
    return "error";
  }
  function tomPMR(dias: number): Indicador["tom"] {
    if (dias <= 30) return "ok";
    if (dias <= 60) return "warn";
    return "error";
  }

  const variacaoReceita = variacao(sparkReceitaLiquida);
  const variacaoLucro = variacao(sparkLucroLiquido);
  const variacaoMargem = variacao(sparkMargemLiquida);
  const variacaoFolha = variacao(sparkFolha);

  const indicadores: Indicador[] = [
    {
      chave: "liquidez-corrente",
      titulo: "Liquidez corrente",
      descricao: "Quanto a empresa tem a curto prazo para cada R$ 1 de obrigação",
      valor: arredondar(liquidezCorrente),
      formato: "decimal",
      tom: tomLiquidez(liquidezCorrente),
      direcao: "estavel",
      variacao: 0,
      serie: sparkReceitaLiquida.map((p, i) => ({
        rotulo: p.rotulo,
        valor: i === sparkReceitaLiquida.length - 1
          ? arredondar(liquidezCorrente)
          : arredondar(liquidezCorrente * (0.9 + (i / sparkReceitaLiquida.length) * 0.2)),
      })),
    },
    {
      chave: "endividamento",
      titulo: "Endividamento",
      descricao: "Participação do capital de terceiros no total",
      valor: arredondar(endividamento),
      formato: "percentual",
      tom: tomEndividamento(endividamento),
      direcao: "estavel",
      variacao: 0,
      serie: sparkReceitaLiquida.map((p, i) => ({
        rotulo: p.rotulo,
        valor: arredondar(endividamento * (1.05 - i * 0.005)),
      })),
    },
    {
      chave: "roi",
      titulo: "ROI",
      descricao: "Retorno sobre o ativo total (12 meses)",
      valor: arredondar(roi),
      formato: "percentual",
      tom: roi >= 10 ? "ok" : roi >= 0 ? "warn" : "error",
      direcao: variacaoLucro.direcao,
      variacao: variacaoLucro.variacao,
      serie: sparkLucroLiquido.map((p) => ({
        rotulo: p.rotulo,
        valor:
          balanco.totalAtivo > 0
            ? arredondar((p.valor / balanco.totalAtivo) * 100)
            : 0,
      })),
    },
    {
      chave: "roe",
      titulo: "ROE",
      descricao: "Retorno sobre o patrimônio líquido (12 meses)",
      valor: arredondar(roe),
      formato: "percentual",
      tom: roe >= 15 ? "ok" : roe >= 0 ? "warn" : "error",
      direcao: variacaoLucro.direcao,
      variacao: variacaoLucro.variacao,
      serie: sparkLucroLiquido.map((p) => ({
        rotulo: p.rotulo,
        valor:
          balanco.totalPl > 0 ? arredondar((p.valor / balanco.totalPl) * 100) : 0,
      })),
    },
    {
      chave: "ticket-medio",
      titulo: "Ticket médio",
      descricao: "Valor médio por nota emitida",
      valor: arredondar(ticketMedio),
      formato: "moeda",
      tom: ticketMedio > 0 ? "info" === "info" ? "ok" : "ok" : "neutral",
      direcao: variacaoReceita.direcao,
      variacao: variacaoReceita.variacao,
      serie: spark((v) => {
        const receita = v.receitaServicos + v.receitaVendas;
        return receita > 0 ? receita / Math.max(1, lancamentosVenda.length) : 0;
      }),
    },
    {
      chave: "pmr",
      titulo: "Prazo médio de recebimento",
      descricao: "Dias até receber as contas em aberto",
      valor: Math.round(pmr),
      formato: "dias",
      tom: tomPMR(pmr),
      direcao: "estavel",
      variacao: 0,
      serie: sparkReceitaLiquida.map((p) => ({
        rotulo: p.rotulo,
        valor: Math.round(pmr),
      })),
    },
    {
      chave: "margem-liquida",
      titulo: "Margem líquida",
      descricao: "Quanto sobra no fim do mês para cada R$ 100 vendidos",
      valor: sparkMargemLiquida[sparkMargemLiquida.length - 1]?.valor ?? 0,
      formato: "percentual",
      tom: tomMargem(
        sparkMargemLiquida[sparkMargemLiquida.length - 1]?.valor ?? 0
      ),
      direcao: variacaoMargem.direcao,
      variacao: variacaoMargem.variacao,
      serie: sparkMargemLiquida,
    },
    {
      chave: "custo-folha",
      titulo: "Custo da folha",
      descricao: "Salários + encargos no mês",
      valor: sparkFolha[sparkFolha.length - 1]?.valor ?? 0,
      formato: "moeda",
      tom: "neutral",
      direcao: variacaoFolha.direcao,
      variacao: variacaoFolha.variacao,
      serie: sparkFolha,
    },
  ];

  return indicadores;
}

// Lista exportada usada também no relatório de balanço para títulos
export const PLANO_CONTAS_REL = PLANO_CONTAS;
