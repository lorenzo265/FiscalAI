import type { AnexoSimples } from "@/lib/schemas/empresa";

interface FaixaSimples {
  ate: number;
  aliquota: number;
  deducao: number;
}

const TABELAS: Record<AnexoSimples, FaixaSimples[]> = {
  I: [
    { ate: 180_000, aliquota: 0.04, deducao: 0 },
    { ate: 360_000, aliquota: 0.073, deducao: 5_940 },
    { ate: 720_000, aliquota: 0.095, deducao: 13_860 },
    { ate: 1_800_000, aliquota: 0.107, deducao: 22_500 },
    { ate: 3_600_000, aliquota: 0.143, deducao: 87_300 },
    { ate: 4_800_000, aliquota: 0.19, deducao: 378_000 },
  ],
  II: [
    { ate: 180_000, aliquota: 0.045, deducao: 0 },
    { ate: 360_000, aliquota: 0.078, deducao: 5_940 },
    { ate: 720_000, aliquota: 0.1, deducao: 13_860 },
    { ate: 1_800_000, aliquota: 0.112, deducao: 22_500 },
    { ate: 3_600_000, aliquota: 0.147, deducao: 85_500 },
    { ate: 4_800_000, aliquota: 0.3, deducao: 720_000 },
  ],
  III: [
    { ate: 180_000, aliquota: 0.06, deducao: 0 },
    { ate: 360_000, aliquota: 0.112, deducao: 9_360 },
    { ate: 720_000, aliquota: 0.135, deducao: 17_640 },
    { ate: 1_800_000, aliquota: 0.16, deducao: 35_640 },
    { ate: 3_600_000, aliquota: 0.21, deducao: 125_640 },
    { ate: 4_800_000, aliquota: 0.33, deducao: 648_000 },
  ],
  IV: [
    { ate: 180_000, aliquota: 0.045, deducao: 0 },
    { ate: 360_000, aliquota: 0.09, deducao: 8_100 },
    { ate: 720_000, aliquota: 0.102, deducao: 12_420 },
    { ate: 1_800_000, aliquota: 0.14, deducao: 39_780 },
    { ate: 3_600_000, aliquota: 0.22, deducao: 183_780 },
    { ate: 4_800_000, aliquota: 0.33, deducao: 828_000 },
  ],
  V: [
    { ate: 180_000, aliquota: 0.155, deducao: 0 },
    { ate: 360_000, aliquota: 0.18, deducao: 4_500 },
    { ate: 720_000, aliquota: 0.195, deducao: 9_900 },
    { ate: 1_800_000, aliquota: 0.205, deducao: 17_100 },
    { ate: 3_600_000, aliquota: 0.23, deducao: 62_100 },
    { ate: 4_800_000, aliquota: 0.305, deducao: 540_000 },
  ],
};

export interface CalculoDAS {
  rbt12: number;
  receitaMes: number;
  faixa: number;
  aliquotaNominal: number;
  aliquotaEfetiva: number;
  deducao: number;
  valorDAS: number;
  anexo: AnexoSimples;
}

export function calcularDAS({
  rbt12,
  receitaMes,
  anexo,
}: {
  rbt12: number;
  receitaMes: number;
  anexo: AnexoSimples;
}): CalculoDAS {
  const tabela = TABELAS[anexo];
  let faixa = 0;
  let regra = tabela[0]!;
  for (let i = 0; i < tabela.length; i++) {
    if (rbt12 <= tabela[i]!.ate) {
      faixa = i;
      regra = tabela[i]!;
      break;
    }
    regra = tabela[i]!;
    faixa = i;
  }

  const aliquotaEfetiva =
    rbt12 > 0
      ? Math.max(0, (rbt12 * regra.aliquota - regra.deducao) / rbt12)
      : regra.aliquota;
  const valorDAS = Math.max(0, receitaMes * aliquotaEfetiva);

  return {
    rbt12,
    receitaMes,
    faixa: faixa + 1,
    aliquotaNominal: regra.aliquota,
    aliquotaEfetiva,
    deducao: regra.deducao,
    valorDAS,
    anexo,
  };
}

export function calcularProximoVencimentoDAS(hoje: Date = new Date()): Date {
  const ano = hoje.getMonth() === 11 ? hoje.getFullYear() + 1 : hoje.getFullYear();
  const mes = hoje.getMonth() === 11 ? 0 : hoje.getMonth() + 1;
  return new Date(ano, mes, 20);
}
