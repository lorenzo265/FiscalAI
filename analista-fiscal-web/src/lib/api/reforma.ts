/**
 * Adapter de domínio: reforma tributária CBS/IBS (Marco 4 — pontas soltas).
 *
 * Liga a tela `/fiscal/reforma-tributaria` (antes 100% estática, com impacto
 * "chutado" em `fat * 0.082` vs `fat * 0.094`) ao cálculo real do backend
 * (`GET /v1/empresas/{id}/reforma/simulacao`). O cálculo é INFORMACIONAL — o
 * backend devolve `observacao_estimativa` (disclaimer) que a tela exibe.
 *
 * Dinheiro chega como string decimal (NUMERIC no Postgres). Para EXIBIÇÃO de
 * uma estimativa, convertemos para `number` (mesma decisão de `faturamento12m`
 * em `empresa.ts`: caminho de exibição, NÃO de precisão monetária).
 */
import { z } from "zod";

import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import { ApiError, fetchJson } from "@/lib/http";

export type FaseReforma =
  | "teste_2026"
  | "transicao_2027_2032"
  | "regime_pleno_2033";

export type CenarioNome = "pessimista" | "realista" | "otimista";

// ── Schema cru do backend (camelCase, pós-toCamel; Decimal → string) ──────────

const cargaSchema = z.object({
  pis: z.string(),
  cofins: z.string(),
  icms: z.string(),
  iss: z.string(),
  total: z.string(),
});

const cenarioSchema = z.object({
  cenario: z.enum(["pessimista", "realista", "otimista"]),
  aliquotaTotal: z.string(),
  cbsProjetada: z.string(),
  ibsProjetada: z.string(),
  totalProjetado: z.string(),
  deltaAbsoluto: z.string(),
  deltaPercentual: z.string(),
});

const simulacaoOutSchema = z.object({
  faseAtual: z.enum(["teste_2026", "transicao_2027_2032", "regime_pleno_2033"]),
  receitaAnualizada: z.string(),
  cargaAtual: cargaSchema,
  cenarios: z.array(cenarioSchema),
  observacaoEstimativa: z.string(),
  algoritmoVersao: z.string(),
});

// ── Shape de exibição (numbers prontos para o formatador) ─────────────────────

export interface CenarioReforma {
  cenario: CenarioNome;
  aliquotaTotal: number;
  totalProjetado: number;
  deltaAbsoluto: number;
  deltaPercentual: number;
}

export interface SimulacaoReforma {
  faseAtual: FaseReforma;
  receitaAnualizada: number;
  cargaAtualTotal: number;
  cenarios: CenarioReforma[];
  /** Disclaimer oficial do backend — sempre preenchido. */
  observacaoEstimativa: string;
}

function num(s: string): number {
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

export const reforma = {
  /**
   * `GET /v1/empresas/{id}/reforma/simulacao?ano_alvo=` — simulação CBS/IBS.
   * `anoAlvo` default 2033 (regime pleno), que é o comparativo "pós-reforma".
   */
  simulacao: async (anoAlvo = 2033): Promise<SimulacaoReforma> => {
    const id = getEmpresaIdAtiva();
    if (!id) {
      throw new ApiError(
        0,
        "EmpresaNaoSelecionada",
        "Selecione uma empresa para simular a reforma."
      );
    }
    const out = await fetchJson(
      `/empresas/${id}/reforma/simulacao?ano_alvo=${anoAlvo}`,
      simulacaoOutSchema
    );
    return {
      faseAtual: out.faseAtual,
      receitaAnualizada: num(out.receitaAnualizada),
      cargaAtualTotal: num(out.cargaAtual.total),
      cenarios: out.cenarios.map((c) => ({
        cenario: c.cenario,
        aliquotaTotal: num(c.aliquotaTotal),
        totalProjetado: num(c.totalProjetado),
        deltaAbsoluto: num(c.deltaAbsoluto),
        deltaPercentual: num(c.deltaPercentual),
      })),
      observacaoEstimativa: out.observacaoEstimativa,
    };
  },
};
