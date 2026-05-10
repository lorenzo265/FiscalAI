import type { LancamentoContabil } from "@/lib/schemas/contabil";
import type { Empresa } from "@/lib/schemas/empresa";
import type { NotaFiscal } from "@/lib/schemas/nota";

function id(prefixo: string, n: number): string {
  return `${prefixo}-${String(n).padStart(6, "0")}`;
}

export function gerarLancamentosDeNotas(
  notas: NotaFiscal[]
): LancamentoContabil[] {
  const out: LancamentoContabil[] = [];
  let seq = 0;

  for (const nota of notas) {
    if (nota.status === "cancelada") continue;
    const data = nota.emitidaEm.slice(0, 10);

    if (nota.tipo === "saida") {
      const ehServico = nota.itens.some((i) => i.aliquotaIss !== undefined);
      const contaReceita = ehServico ? "4.1.1" : "4.1.2";

      // Reconhece receita: D Clientes a Receber  C Receita de Serviços/Vendas
      out.push({
        id: id("nf", ++seq),
        data,
        contaDebito: "1.1.2.01",
        contaCredito: contaReceita,
        valor: nota.totais.valorNota,
        historico: `NF-e ${nota.numero} · ${nota.contraparte.nome}`,
        origem: "nf_saida",
        origemRefId: nota.chave,
        confianca: 1,
        criadoEm: nota.emitidaEm,
      });

      // Imposto sobre vendas (DAS no Simples): D Despesa Tributária  C DAS a Recolher
      if (nota.totais.totalImpostos > 0) {
        out.push({
          id: id("nf-imp", ++seq),
          data,
          contaDebito: "5.1.5",
          contaCredito: "2.1.2.01",
          valor: nota.totais.totalImpostos,
          historico: `Tributos s/ NF ${nota.numero}`,
          origem: "fiscal",
          origemRefId: nota.chave,
          confianca: 1,
          criadoEm: nota.emitidaEm,
        });
      }
    } else {
      // Entrada: classifica simplificadamente como serviços de terceiros.
      out.push({
        id: id("nf", ++seq),
        data,
        contaDebito: "5.1.3",
        contaCredito: "2.1.1.01",
        valor: nota.totais.valorNota,
        historico: `NF entrada ${nota.numero} · ${nota.razaoEmitente}`,
        origem: "nf_entrada",
        origemRefId: nota.chave,
        confianca: nota.manifesto === "confirmada" ? 1 : 0.7,
        criadoEm: nota.emitidaEm,
      });
    }
  }

  return out;
}

export function gerarLancamentosBancariosMock(
  empresa: Empresa,
  hoje: Date = new Date()
): LancamentoContabil[] {
  const out: LancamentoContabil[] = [];
  const inicio = new Date(hoje.getFullYear(), hoje.getMonth() - 5, 1);
  let seq = 0;

  // Capital social inicial.
  out.push({
    id: id("cap", ++seq),
    data: empresa.criadoEm.slice(0, 10),
    contaDebito: "1.1.1.02",
    contaCredito: "3.1.1",
    valor: 50_000,
    historico: "Integralização de capital social",
    origem: "manual",
    confianca: 1,
    criadoEm: empresa.criadoEm,
  });

  for (let m = 0; m < 6; m++) {
    const ref = new Date(inicio.getFullYear(), inicio.getMonth() + m, 1);
    const dataFolha = new Date(ref.getFullYear(), ref.getMonth(), 5)
      .toISOString()
      .slice(0, 10);
    const dataAluguel = new Date(ref.getFullYear(), ref.getMonth(), 10)
      .toISOString()
      .slice(0, 10);
    const dataTarifa = new Date(ref.getFullYear(), ref.getMonth(), 28)
      .toISOString()
      .slice(0, 10);

    out.push({
      id: id("folha", ++seq),
      data: dataFolha,
      contaDebito: "5.1.1",
      contaCredito: "1.1.1.02",
      valor: 14_500,
      historico: "Folha de pagamento e encargos do mês",
      origem: "folha",
      confianca: 1,
      criadoEm: dataFolha,
    });

    out.push({
      id: id("aluguel", ++seq),
      data: dataAluguel,
      contaDebito: "5.1.2",
      contaCredito: "1.1.1.02",
      valor: 4_800,
      historico: "Aluguel da sede",
      origem: "bancario",
      confianca: 0.95,
      criadoEm: dataAluguel,
    });

    out.push({
      id: id("tarifa", ++seq),
      data: dataTarifa,
      contaDebito: "5.2.1",
      contaCredito: "1.1.1.02",
      valor: 142,
      historico: "Tarifa bancária mensal",
      origem: "bancario",
      // Algumas tarifas vêm com baixa confiança pra simular OCR/match incerto.
      confianca: m % 2 === 0 ? 0.55 : 0.92,
      criadoEm: dataTarifa,
    });
  }

  return out;
}
