import { calcularDAS, calcularProximoVencimentoDAS } from "@/lib/fiscal/calcula-das";
import type { Empresa } from "@/lib/schemas/empresa";
import type { GuiaDAS } from "@/lib/schemas/guias";

const MESES_ABREV = [
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

export function gerarGuiasMock(empresa: Empresa, hoje: Date = new Date()): GuiaDAS[] {
  const fat12 = empresa.faturamento12m;
  const anexo = empresa.anexoSimples ?? "III";
  const out: GuiaDAS[] = [];

  for (let i = 11; i >= 0; i--) {
    const ref = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    const ano = ref.getFullYear();
    const mes = ref.getMonth() + 1;
    const variacao = 0.85 + ((i * 7 + ref.getMonth()) % 30) / 100;
    const receitaMes = Math.round((fat12 / 12) * variacao);
    const calc = calcularDAS({ rbt12: fat12, receitaMes, anexo });
    const vencimentoDate = new Date(ano, mes, 20); // dia 20 do mês seguinte ao período
    const vencimento = vencimentoDate.toISOString().slice(0, 10);
    const isAtual = i === 0;
    const isFuturo = vencimentoDate > hoje;

    const status: GuiaDAS["status"] = isAtual
      ? "em_aberto"
      : isFuturo
        ? "em_aberto"
        : "pago";
    const pagaEm = status === "pago"
      ? new Date(ano, mes, 18 - ((i * 3) % 4)).toISOString().slice(0, 10)
      : null;

    const numeroDocumento = `${ano}${String(mes).padStart(2, "0")}${String(2451 + i * 17).padStart(6, "0")}`;
    const codigoBarras = gerarCodigoBarras44(numeroDocumento, calc.valorDAS);

    out.push({
      id: `das-${ano}-${String(mes).padStart(2, "0")}`,
      periodo: { ano, mes },
      rotulo: `${MESES_ABREV[mes - 1]}/${String(ano).slice(2)}`,
      numeroDocumento,
      codigoBarras,
      faturamentoMes: receitaMes,
      aliquotaEfetiva: calc.aliquotaEfetiva,
      valor: Math.round(calc.valorDAS * 100) / 100,
      vencimento,
      pagaEm,
      status,
      pixCopiaCola: gerarPixCopiaCola(empresa, calc.valorDAS, numeroDocumento),
    });
  }

  return out.reverse();
}

export function obterProximaGuiaVencimento(hoje: Date = new Date()): string {
  return calcularProximoVencimentoDAS(hoje).toISOString().slice(0, 10);
}

function gerarCodigoBarras44(num: string, valor: number): string {
  const valorCent = String(Math.round(valor * 100)).padStart(11, "0");
  const base = `85800000${valorCent}${num}`;
  return base.padEnd(44, "0").slice(0, 44);
}

function gerarPixCopiaCola(empresa: Empresa, valor: number, doc: string): string {
  // Mock determinístico — não é um BR Code real, é só um string parecido.
  const cnpj = empresa.cnpj.padStart(14, "0").slice(-14);
  const v = valor.toFixed(2);
  return [
    "00020126",
    "5204000053039865802BR",
    "59" + String(cnpj.length).padStart(2, "0") + cnpj,
    "60" + String(empresa.razaoSocial.length).padStart(2, "0") + empresa.razaoSocial.slice(0, 25),
    "62" + String(doc.length + 4).padStart(2, "0") + "05" + String(doc.length).padStart(2, "0") + doc,
    "54" + String(v.length).padStart(2, "0") + v,
    "6304MOCK",
  ].join("");
}
