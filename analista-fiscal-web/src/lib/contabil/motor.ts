import { PLANO_CONTAS, buscarConta } from "@/lib/mocks/seeds/plano-contas";
import type {
  ContaContabil,
  LancamentoContabil,
  LinhaBalancete,
  NaturezaConta,
} from "@/lib/schemas/contabil";

const NATUREZAS_DEVEDORAS: NaturezaConta[] = ["ativo", "despesa"];

// Calcula o sinal do saldo: ativo/despesa = D - C, passivo/PL/receita = C - D.
function aplicarSinal(natureza: NaturezaConta, debitos: number, creditos: number): number {
  if (NATUREZAS_DEVEDORAS.includes(natureza)) {
    return debitos - creditos;
  }
  return creditos - debitos;
}

export interface TotaisBalancete {
  totalDebitos: number;
  totalCreditos: number;
  fechado: boolean;
}

export function montarBalancete(
  lancamentos: LancamentoContabil[]
): { raizes: LinhaBalancete[]; totais: TotaisBalancete } {
  const debitoPorConta = new Map<string, number>();
  const creditoPorConta = new Map<string, number>();

  for (const l of lancamentos) {
    debitoPorConta.set(
      l.contaDebito,
      (debitoPorConta.get(l.contaDebito) ?? 0) + l.valor
    );
    creditoPorConta.set(
      l.contaCredito,
      (creditoPorConta.get(l.contaCredito) ?? 0) + l.valor
    );
  }

  const linhas = new Map<string, LinhaBalancete>();
  for (const conta of PLANO_CONTAS) {
    const debitos = debitoPorConta.get(conta.codigo) ?? 0;
    const creditos = creditoPorConta.get(conta.codigo) ?? 0;
    linhas.set(conta.codigo, {
      conta,
      saldoAnterior: 0,
      debitos,
      creditos,
      saldoAtual: aplicarSinal(conta.natureza, debitos, creditos),
      filhos: [],
    });
  }

  const raizes: LinhaBalancete[] = [];
  for (const conta of PLANO_CONTAS) {
    const linha = linhas.get(conta.codigo)!;
    if (conta.pai) {
      const pai = linhas.get(conta.pai);
      pai?.filhos.push(linha);
    } else {
      raizes.push(linha);
    }
  }

  // Agrega valores de filhos pra pais (sintéticas).
  function agregar(linha: LinhaBalancete): void {
    if (linha.filhos.length === 0) return;
    let d = 0;
    let c = 0;
    for (const f of linha.filhos) {
      agregar(f);
      d += f.debitos;
      c += f.creditos;
    }
    linha.debitos = d;
    linha.creditos = c;
    linha.saldoAtual = aplicarSinal(linha.conta.natureza, d, c);
  }
  raizes.forEach(agregar);

  let totalDebitos = 0;
  let totalCreditos = 0;
  for (const l of lancamentos) {
    totalDebitos += l.valor;
    totalCreditos += l.valor;
  }

  return {
    raizes,
    totais: {
      totalDebitos,
      totalCreditos,
      fechado: Math.abs(totalDebitos - totalCreditos) < 0.005,
    },
  };
}

export interface RazaoLinha {
  lancamento: LancamentoContabil;
  contraparte: string;
  debito: number;
  credito: number;
  saldoApos: number;
}

export function montarRazao(
  conta: ContaContabil,
  lancamentos: LancamentoContabil[]
): RazaoLinha[] {
  const movimentos = lancamentos
    .filter(
      (l) => l.contaDebito === conta.codigo || l.contaCredito === conta.codigo
    )
    .sort((a, b) => a.data.localeCompare(b.data));

  let saldo = 0;
  const out: RazaoLinha[] = [];
  for (const l of movimentos) {
    const ehDebito = l.contaDebito === conta.codigo;
    const debito = ehDebito ? l.valor : 0;
    const credito = ehDebito ? 0 : l.valor;
    const sinal = NATUREZAS_DEVEDORAS.includes(conta.natureza)
      ? debito - credito
      : credito - debito;
    saldo += sinal;
    const contraCodigo = ehDebito ? l.contaCredito : l.contaDebito;
    const contraNome = buscarConta(contraCodigo)?.nome ?? contraCodigo;
    out.push({
      lancamento: l,
      contraparte: contraNome,
      debito,
      credito,
      saldoApos: saldo,
    });
  }
  return out;
}

export function calcularResultadoExercicio(
  lancamentos: LancamentoContabil[]
): { receita: number; despesa: number; resultado: number } {
  let receita = 0;
  let despesa = 0;
  for (const l of lancamentos) {
    const cD = buscarConta(l.contaDebito);
    const cC = buscarConta(l.contaCredito);
    if (cC?.natureza === "receita") {
      receita += l.valor;
    }
    if (cD?.natureza === "despesa") {
      despesa += l.valor;
    }
  }
  return { receita, despesa, resultado: receita - despesa };
}
