/**
 * Adapter de domínio: COFRE DE CERTIFICADO A1.
 *
 * Liga a tela de configurações → certificado ao módulo backend `certificado`:
 *
 *   GET    /v1/empresas/{id}/certificado   → status (metadados) ou null (404)
 *   POST   /v1/empresas/{id}/certificado   → sobe/substitui (.p12 base64 + senha)
 *   DELETE /v1/empresas/{id}/certificado   → desativa
 *
 * O .p12 e a senha vão para o backend, que os guarda CIFRADOS em repouso
 * (AES-256-GCM). A resposta nunca traz o material — só metadados (CN, CNPJ,
 * validade, fingerprint).
 */
import { z } from "zod";

import { ApiError, fetchJson, toSnake } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";

function rotaEmpresa(sufixo: string): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      0,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada. Entre na conta e escolha uma empresa."
    );
  }
  return `/empresas/${id}${sufixo}`;
}

/** `CertificadoStatusOut` do backend (metadados; nunca o .p12/senha). */
export const certificadoStatusSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  cnTitular: z.string(),
  cnpjTitular: z.string().nullable(),
  validadeInicio: z.string(),
  validadeFim: z.string(),
  fingerprint: z.string(),
  ativo: z.boolean(),
  criadoEm: z.string(),
});
export type CertificadoStatus = z.infer<typeof certificadoStatusSchema>;

const remocaoSchema = z.object({ removido: z.boolean() });

export interface SubirCertificadoInput {
  /** Conteúdo do .p12/.pfx em base64 (sem o prefixo data:). */
  pfxBase64: string;
  /** Senha do certificado. */
  senha: string;
}

export const certificado = {
  /** Status do cert ativo, ou `null` quando a empresa não tem cert (404). */
  status: async (): Promise<CertificadoStatus | null> => {
    try {
      return await fetchJson(rotaEmpresa("/certificado"), certificadoStatusSchema);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },

  /** Sobe (ou substitui) o certificado A1. Backend valida e cifra. */
  subir: (input: SubirCertificadoInput): Promise<CertificadoStatus> =>
    fetchJson(rotaEmpresa("/certificado"), certificadoStatusSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        toSnake({ pfxBase64: input.pfxBase64, senha: input.senha })
      ),
    }),

  /** Desativa o certificado ativo da empresa. */
  remover: (): Promise<{ removido: boolean }> =>
    fetchJson(rotaEmpresa("/certificado"), remocaoSchema, { method: "DELETE" }),
};
