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
import { ApiError } from "@/lib/http";
import type {
  Certidao,
  CompliancePainel,
  Intimacao,
  Parcelamento,
  StatusIntimacao,
} from "@/lib/schemas/compliance";

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
  painel: (): Promise<CompliancePainel> => compliancePainel(),
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
