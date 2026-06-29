/**
 * Adapter de domínio: compliance (Onda 2 / Fase E — integração com a API real).
 *
 * Certidões e parcelamentos vêm do backend FastAPI (`fetchJson` +
 * `getEmpresaIdAtiva`); intimações, painel agregado e "enviar ao contador"
 * permanecem locais (Dexie/derivado) porque o backend ainda NÃO expõe esses
 * endpoints — ver gaps documentados em `@/lib/compliance/db-service`.
 *
 * Assinaturas de `compliance.*` preservadas (consumidas por `useCompliance`).
 *
 * Dono na integração: agente de domínio compliance.
 */
import { z } from "zod";

import {
  atualizarStatusIntimacao,
  compliancePainel,
  enviarIntimacaoAoContador,
  listarCertidoes,
  listarIntimacoes,
  listarParcelamentos,
  obterIntimacao,
  renovarCertidao,
} from "@/lib/compliance/db-service";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import { ApiError, fetchJson } from "@/lib/http";
import type {
  Certidao,
  CompliancePainel,
  Intimacao,
  Parcelamento,
  StatusIntimacao,
} from "@/lib/schemas/compliance";

// ── Situação cadastral RFB (GET /empresas/{id}/monitor/rfb/atual) ──────────────

const statusRfbSchema = z.object({
  situacaoCadastral: z.enum(["ativa", "suspensa", "inapta", "baixada", "nula"]),
  dataSituacao: z.string().nullable().optional(),
  motivoSituacao: z.string().nullable().optional(),
});

/** `true` ativa, `false` suspensa/inapta/etc., `null` se ainda não há snapshot. */
async function situacaoCadastralAtiva(): Promise<boolean | null> {
  const id = getEmpresaIdAtiva();
  if (!id) return null;
  try {
    const r = await fetchJson(`/empresas/${id}/monitor/rfb/atual`, statusRfbSchema);
    return r.situacaoCadastral === "ativa";
  } catch {
    // 404 (sem snapshot do monitor ainda) ou serviço fora → não bloqueia o painel.
    return null;
  }
}

// ── e-CAC (Receita) ────────────────────────────────────────────────────────────

const mensagemEcacSchema = z.object({
  id: z.string(),
  assunto: z.string(),
  recebidaEm: z.string(),
  lidaEm: z.string().nullable().optional(),
  tipo: z.enum(["intimacao", "aviso", "informativa", "outro"]).nullable().optional(),
  prioridade: z.enum(["alta", "media", "baixa"]).nullable().optional(),
  prazoResposta: z.string().nullable().optional(),
  encaminhadaMarketplace: z.boolean(),
});
export type MensagemEcac = z.infer<typeof mensagemEcacSchema>;

const syncEcacSchema = z.object({
  novas: z.number(),
  classificadas: z.number(),
  totalNoLote: z.number(),
  aviso: z.string().nullable().optional(),
});
export type SyncEcacResultado = z.infer<typeof syncEcacSchema>;

/** Traduz `ApiError.codigo` em mensagem amigável (nunca vaza código cru). */
export function mensagemAmigavelCompliance(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não foi possível concluir a operação de compliance agora. Tente novamente.";
  }
  switch (err.codigo) {
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa para ver suas certidões e parcelamentos.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione uma empresa ativa.";
    case "CertidaoEmissaoFalhou":
      return "O órgão emissor não respondeu. A solicitação ficou em processamento.";
    case "ParcelamentoNaoEncontrado":
      return "Parcelamento não encontrado para esta empresa.";
    case "FocusNfeTimeout":
    case "LLMIndisponivel":
      return "O serviço externo está indisponível no momento. Tente novamente em instantes.";
    case "FalhaDeRede":
      return "Sem conexão com o servidor. Verifique sua internet e tente de novo.";
    default:
      return (
        err.mensagem ||
        "Não foi possível concluir a operação de compliance agora."
      );
  }
}

export const compliance = {
  /**
   * Painel agregado (Dexie) + situação cadastral RFB real (quando há snapshot).
   * O `cnpjAtivo` deixa de ser hardcoded `true`: lê `GET /monitor/rfb/atual` e,
   * só quando há dado, sobrepõe; sem snapshot mantém o default do painel.
   */
  painel: async (): Promise<CompliancePainel> => {
    const base = await compliancePainel();
    const ativa = await situacaoCadastralAtiva();
    return ativa === null ? base : { ...base, cnpjAtivo: ativa };
  },
  /** `POST /empresas/{id}/e-cac/sync` — puxa novas mensagens da Receita. */
  sincronizarEcac: async (): Promise<SyncEcacResultado> => {
    const id = getEmpresaIdAtiva();
    if (!id) {
      throw new ApiError(
        0,
        "EmpresaNaoSelecionada",
        "Selecione uma empresa para sincronizar com a Receita."
      );
    }
    return fetchJson(`/empresas/${id}/e-cac/sync`, syncEcacSchema, {
      method: "POST",
    });
  },
  /** `GET /empresas/{id}/e-cac/mensagens` — mensagens reais do e-CAC. */
  listarMensagensEcac: async (): Promise<MensagemEcac[]> => {
    const id = getEmpresaIdAtiva();
    if (!id) return [];
    return fetchJson(`/empresas/${id}/e-cac/mensagens`, z.array(mensagemEcacSchema));
  },
  listarCertidoes: (): Promise<Certidao[]> => listarCertidoes(),
  renovarCertidao: (id: string): Promise<Certidao | undefined> =>
    renovarCertidao(id),
  listarIntimacoes: (): Promise<Intimacao[]> => listarIntimacoes(),
  obterIntimacao: (id: string): Promise<Intimacao | undefined> =>
    obterIntimacao(id),
  marcarIntimacaoLida: (id: string): Promise<void> =>
    atualizarStatusIntimacao(id, "lida"),
  atualizarStatusIntimacao: (
    id: string,
    status: StatusIntimacao
  ): Promise<void> => atualizarStatusIntimacao(id, status),
  enviarAoContador: (id: string): Promise<void> =>
    enviarIntimacaoAoContador(id),
  listarParcelamentos: (): Promise<Parcelamento[]> => listarParcelamentos(),
};
