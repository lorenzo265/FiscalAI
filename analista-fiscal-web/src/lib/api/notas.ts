/**
 * Adapter de domínio: NOTAS (Onda 1 · Fase C — integração com o backend real).
 *
 * O backend FiscalAI expõe, hoje, QUATRO endpoints para o domínio de notas
 * (confirmados via `http://localhost:8000/openapi.json`):
 *
 *   1. `GET    /v1/empresas/{id}/documentos`           → lista de DocumentoFiscalOut
 *   2. `POST   /v1/empresas/{id}/ingestao/upload`      → ingerir NF-e/NFC-e (XML)
 *   3. `POST   /v1/empresas/{id}/notas/nfse`           → emitir NFS-e (Focus, 202)
 *   4. `GET    /v1/empresas/{id}/notas/nfse/{ref}`     → status da NFS-e (polling)
 *
 * O FRONT, por outro lado, trata notas como um CRUD rico (listar / obter /
 * emitir / cancelar / carta-correção / manifestar) com catálogo de produtos e
 * contrapartes. Boa parte desse CRUD NÃO tem correspondência no backend ainda
 * — ver «Gaps de contrato» no relatório da Fase C. Aqui implementamos a ponte
 * HONESTA: tudo que o backend fornece é falado de verdade via `fetchJson`; o
 * que ele não fornece permanece como dado LOCAL de apoio (Dexie/seed), nunca
 * fabricando fato fiscal.
 *
 * Invariantes preservados (ver `hadoff-front-back.md` › Apêndice):
 *  - Token via header (injetado pelo `fetchJson`); tenant via JWT; `empresa_id`
 *    na rota (montada com `getEmpresaIdAtiva()`).
 *  - CFOP/CST/NCM NUNCA expostos crus ao usuário — as telas traduzem; aqui só
 *    repassamos os códigos para a camada de tradução, jamais como rótulo final.
 *  - Erros de domínio (`FocusNfeTimeout` 504, `FocusNfeErro`, etc.) viram
 *    mensagem amigável via `mensagemAmigavelNotas`.
 */
import { z } from "zod";

import { ApiError, fetchJson, toSnake } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import {
  contraparteSchema,
  produtoCatalogoSchema,
  type Contraparte,
  type ProdutoCatalogo,
} from "@/lib/schemas/nota";
import { CONTRAPARTES_MOCK } from "@/lib/mocks/seeds/contrapartes";
import { CATALOGO_PRODUTOS } from "@/lib/mocks/seeds/catalogo-produtos";

// ── helper de rota ───────────────────────────────────────────────────────────

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

// ── shapes REAIS do backend (camelCase, pós-`toCamel`) ───────────────────────

/**
 * `DocumentoFiscalOut` do backend (`app/modules/ingestao/schemas.py`). Dinheiro
 * chega como STRING decimal (`NUMERIC(14,2)`) — preservado como string aqui; a
 * conversão para number acontece só no mapper para `NotaFiscal` (cujo schema
 * legado é number-typed e é consumido aritmeticamente pelas telas).
 */
export const documentoFiscalOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipo: z.string(), // nfe | nfse | nfce …
  direcao: z.string(), // saida | entrada
  chave: z.string().nullable(),
  numero: z.string(),
  serie: z.string(),
  status: z.string(),
  emitidaEm: z.string(),
  cnpjEmitente: z.string(),
  cnpjDestinatario: z.string().nullable(),
  valorTotal: z.string(), // decimal string
  valorIcms: z.string().nullable(),
  valorIpi: z.string().nullable(),
  valorPis: z.string().nullable(),
  valorCofins: z.string().nullable(),
  cfop: z.string().nullable(),
  ncm: z.string().nullable(),
  naturezaOperacao: z.string().nullable(),
  ingestedVia: z.string().nullable(),
  createdAt: z.string(),
});
export type DocumentoFiscalOut = z.infer<typeof documentoFiscalOutSchema>;

const documentosListaSchema = z.array(documentoFiscalOutSchema);

/** `EmitirNfseOut` — resposta imediata (202) da solicitação de emissão. */
export const emitirNfseOutSchema = z.object({
  focusRef: z.string(),
  status: z.string(),
  documentoFiscalId: z.string().nullable().optional(),
  mensagem: z.string(),
  avisoIss: z.string().nullable().optional(),
});
export type EmitirNfseOut = z.infer<typeof emitirNfseOutSchema>;

/** `NfseStatusOut` — status atualizado consultado na Focus NFe. */
export const nfseStatusOutSchema = z.object({
  focusRef: z.string(),
  status: z.string(),
  numero: z.string().nullable().optional(),
  numeroRps: z.string().nullable().optional(),
  pdfUrl: z.string().nullable().optional(),
  xmlUrl: z.string().nullable().optional(),
  mensagemSefaz: z.string().nullable().optional(),
});
export type NfseStatusOut = z.infer<typeof nfseStatusOutSchema>;

/** `IngestaoResultadoOut` — eco do upload de XML. */
export const ingestaoResultadoOutSchema = z.object({
  documento: documentoFiscalOutSchema,
  mensagem: z.string(),
});
export type IngestaoResultadoOut = z.infer<typeof ingestaoResultadoOutSchema>;

// ── entrada de emissão de NFS-e (espelha `EmitirNfseIn` do backend) ──────────

export interface EmitirNfseInput {
  /** 1 = tributação no município, 2 = fora do município. */
  naturezaOperacao: 1 | 2;
  servicoDescricao: string;
  /** Código de serviço municipal (LC 116/2003). */
  servicoCodigo: string;
  /** Valor do serviço (decimal string — NUNCA float). */
  servicoValor: string;
  /** Alíquota ISS em % (2..5). Decimal string. */
  aliquotaIss: string;
  /** Deduções da base de cálculo (decimal string). */
  deducoes?: string;
  /** Tomador PJ: 14 dígitos. */
  cnpjTomador?: string;
  /** Tomador PF: 11 dígitos. */
  cpfTomador?: string;
  razaoSocialTomador?: string;
  emailTomador?: string;
}

// ── superfície pública do adapter ────────────────────────────────────────────

export const notas = {
  // ── 1. documentos fiscais (fonte real da listagem) ──
  /**
   * Lista os documentos fiscais persistidos da empresa ativa (notas de entrada
   * e de saída). Fonte REAL para o `useNotas` via db-service. `tipo`/`direcao`
   * são filtros opcionais do backend.
   */
  listarDocumentos: (
    opts?: { tipo?: string; direcao?: string; limit?: number }
  ): Promise<DocumentoFiscalOut[]> => {
    const qs = new URLSearchParams();
    if (opts?.tipo) qs.set("tipo", opts.tipo);
    if (opts?.direcao) qs.set("direcao", opts.direcao);
    if (opts?.limit) qs.set("limit", String(opts.limit));
    const sufixo = qs.toString() ? `?${qs.toString()}` : "";
    return fetchJson(
      rotaEmpresa(`/documentos${sufixo}`),
      documentosListaSchema
    );
  },

  // ── 2. ingestão de XML (entrada) ──
  /**
   * Ingere uma NF-e/NFC-e de entrada a partir do XML (multipart). Não passa por
   * `fetchJson` (que serializa JSON) — usa `FormData` direto.
   */
  uploadDocumento: async (
    arquivo: File | Blob,
    nomeArquivo = "documento.xml"
  ): Promise<IngestaoResultadoOut> => {
    const form = new FormData();
    form.append("arquivo", arquivo, nomeArquivo);
    return fetchJson(
      rotaEmpresa("/ingestao/upload"),
      ingestaoResultadoOutSchema,
      { method: "POST", body: form }
    );
  },

  // ── 3. emissão de NFS-e (saída de serviço, via Focus) ──
  /**
   * Solicita a emissão de uma NFS-e (assíncrona — 202). O backend só emite
   * NOTA DE SERVIÇO; nota de PRODUTO (NF-e) não tem endpoint de emissão hoje
   * (ver gaps). Acompanhe com `consultarStatusNfse(focusRef)`.
   */
  emitirNfse: (input: EmitirNfseInput): Promise<EmitirNfseOut> =>
    fetchJson(rotaEmpresa("/notas/nfse"), emitirNfseOutSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toSnake(input)),
    }),

  // ── 4. status da NFS-e (polling) ──
  consultarStatusNfse: (focusRef: string): Promise<NfseStatusOut> =>
    fetchJson(
      rotaEmpresa(`/notas/nfse/${encodeURIComponent(focusRef)}`),
      nfseStatusOutSchema
    ),

  // ── catálogo / contraparte (SEM backend — dado LOCAL de apoio) ──
  /**
   * Catálogo de produtos. ⚠️ Não há endpoint no backend — é uma lista de apoio
   * (sugestões de preenchimento), não um fato fiscal. Mantido local (seed).
   * Documentado como gap na Fase C.
   */
  catalogo: (): Promise<ProdutoCatalogo[]> =>
    Promise.resolve(z.array(produtoCatalogoSchema).parse(CATALOGO_PRODUTOS)),

  /**
   * Lookup de contraparte por documento. ⚠️ Sem endpoint dedicado no backend
   * (o cadastro de contraparte do front é local). Resolve a partir do seed
   * local; se não achar, devolve um esqueleto com o documento — NUNCA inventa
   * dados cadastrais (nome fica genérico, sinalizando ausência).
   */
  lookupContraparte: (documento: string): Promise<Contraparte> => {
    const doc = documento.replace(/\D/g, "");
    const achada = CONTRAPARTES_MOCK.find(
      (c) => c.documento.replace(/\D/g, "") === doc
    );
    if (achada) return Promise.resolve(contraparteSchema.parse(achada));
    return Promise.resolve(
      contraparteSchema.parse({
        id: doc,
        tipo: doc.length === 11 ? "pf" : "pj",
        documento: doc,
        nome: "Contraparte não cadastrada",
      })
    );
  },
};

// ── tradução de erro de domínio → mensagem amigável ──────────────────────────

/**
 * Traduz `ApiError.codigo` (do backend) em mensagem amigável de notas. NUNCA
 * vaza o código cru para o usuário PME.
 */
export function mensagemAmigavelNotas(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Não conseguimos concluir a operação com as notas. Tente novamente.";
  }
  switch (err.codigo) {
    case "FocusNfeTimeout":
      return "A prefeitura demorou para responder. A nota pode ainda ser autorizada — verifique o status em instantes.";
    case "FocusNfeErro":
      return "O emissor de notas recusou a solicitação. Confira os dados do serviço e do tomador.";
    case "EmpresaNaoEncontrada":
      return "Empresa não encontrada. Selecione novamente a empresa ativa.";
    case "EmpresaNaoSelecionada":
      return "Selecione uma empresa antes de trabalhar com notas.";
    case "DocumentoJaIngerido":
      return "Esse documento já foi importado anteriormente.";
    case "XmlInvalido":
      return "O arquivo XML enviado é inválido ou está corrompido.";
    default:
      return err.mensagem || "Não foi possível concluir a operação com as notas.";
  }
}
