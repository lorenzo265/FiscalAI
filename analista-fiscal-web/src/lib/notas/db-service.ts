/**
 * Serviço de dados do domínio NOTAS (Onda 1 · Fase C).
 *
 * Casamento front↔back (ver `notas.ts` e o relatório da Fase C):
 *  - `listarNotas` / `obterNota` → fonte REAL `GET …/documentos`
 *    (`DocumentoFiscalOut`), mapeada para `NotaFiscal` via `mapearDocumento`.
 *    Cai para o Dexie (mock/local) se o backend não responder ou se a empresa
 *    ainda não tiver documentos — o app segue utilizável offline/sem seed.
 *  - `salvarNota` (rascunho/emissão) e as ações cancelar / carta-correção /
 *    manifestar permanecem LOCAIS (Dexie): o backend não expõe esses verbos
 *    para o shape rico do front (só emissão de NFS-e de serviço). Gaps
 *    documentados na Fase C — nenhum dado fiscal é inventado.
 *  - catálogo de produtos / contrapartes: dado LOCAL de apoio (sem backend).
 *
 * Dinheiro: o backend manda decimal STRING; o `NotaFiscal` legado é
 * number-typed e consumido aritmeticamente pelas telas (`> 0`, `.toString()`,
 * `formatarMoeda(number)`). A conversão string→number acontece SÓ na fronteira
 * do mapper (`numDecimal`), preservando a precisão de 2 casas do `NUMERIC(14,2)`.
 */
import { getDb } from "@/lib/db";
import type {
  Contraparte,
  NotaFiscal,
  ProdutoCatalogo,
  StatusManifesto,
  StatusNota,
  TipoNota,
} from "@/lib/schemas/nota";
import { notaFiscalSchema } from "@/lib/schemas/nota";
import type { Empresa } from "@/lib/schemas/empresa";
import { gerarNotasIniciais } from "@/lib/mocks/notas";
import { CONTRAPARTES_MOCK } from "@/lib/mocks/seeds/contrapartes";
import { CATALOGO_PRODUTOS } from "@/lib/mocks/seeds/catalogo-produtos";
import { notas as notasApi, type DocumentoFiscalOut } from "@/lib/api/notas";

const SEED_KEY = "analista-fiscal:notas-seeded";

// ── mapeamento DocumentoFiscalOut → NotaFiscal ───────────────────────────────

function numDecimal(v: string | null | undefined): number {
  if (v == null || v === "") return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function mapearDirecao(direcao: string): TipoNota {
  return direcao === "entrada" ? "entrada" : "saida";
}

/**
 * Status do backend → enum de status do front. Mantém cor+ícone+palavra das
 * pills (qualquer valor desconhecido cai em "emitida" = "em processamento").
 */
function mapearStatus(status: string): StatusNota {
  const s = status.toLowerCase();
  if (s.includes("autoriz")) return "autorizada";
  if (s.includes("cancel")) return "cancelada";
  if (s.includes("rejeit")) return "rejeitada";
  if (s.includes("deneg")) return "denegada";
  if (s.includes("rascunho") || s.includes("draft")) return "rascunho";
  return "emitida";
}

/**
 * Mapeia um `DocumentoFiscalOut` (backend) para `NotaFiscal` (front),
 * preenchendo SÓ o que o backend fornece. Campos sem origem no backend
 * (itens detalhados, breakdown de totais por tributo, contraparte com nome /
 * endereço, manifesto, pagamento) ficam vazios/derivados — NÃO são inventados.
 *
 * Se houver uma `NotaFiscal` LOCAL com a mesma chave/numero (rascunho emitido
 * pelo wizard, manifesto registrado, CC-e), ela é mesclada por cima para não
 * perder o estado local que ainda não tem backend.
 */
export function mapearDocumento(
  doc: DocumentoFiscalOut,
  local?: NotaFiscal
): NotaFiscal {
  const tipo = mapearDirecao(doc.direcao);
  const valor = numDecimal(doc.valorTotal);
  const icms = numDecimal(doc.valorIcms);
  const pis = numDecimal(doc.valorPis);
  const cofins = numDecimal(doc.valorCofins);
  const documentoContraparte = doc.cnpjDestinatario ?? "";

  const base: NotaFiscal = {
    id: doc.id,
    // backend permite chave nula (ex.: NFS-e sem chave de 44 díg.). O schema
    // exige 44 — usamos a chave local, senão um placeholder estável (id).
    chave: doc.chave ?? local?.chave ?? doc.id.replace(/\D/g, "").padEnd(44, "0").slice(0, 44),
    numero: doc.numero,
    serie: doc.serie,
    tipo,
    status: mapearStatus(doc.status),
    emitidaEm: doc.emitidaEm,
    cnpjEmitente: doc.cnpjEmitente,
    razaoEmitente: local?.razaoEmitente ?? "",
    contraparte: local?.contraparte ?? {
      id: documentoContraparte || doc.id,
      tipo: documentoContraparte.length === 11 ? "pf" : "pj",
      documento: documentoContraparte,
      nome: local?.contraparte?.nome ?? "",
    },
    itens: local?.itens ?? [],
    totais: local?.totais ?? {
      produtos: valor,
      desconto: 0,
      frete: 0,
      icms,
      iss: 0,
      pis,
      cofins,
      totalImpostos: icms + pis + cofins,
      valorNota: valor,
    },
    pagamento: local?.pagamento,
    observacao: local?.observacao,
    protocoloAutorizacao: local?.protocoloAutorizacao,
    manifesto: local?.manifesto ?? (tipo === "entrada" ? "pendente_manifesto" : undefined),
    canceladaEm: local?.canceladaEm,
    motivoCancelamento: local?.motivoCancelamento,
    cartasCorrecao: local?.cartasCorrecao ?? [],
  };

  // Validação defensiva: se o mapeamento divergir do schema, cai pro local.
  const parsed = notaFiscalSchema.safeParse(base);
  return parsed.success ? parsed.data : (local ?? base);
}

// ── seed local (apoio) ───────────────────────────────────────────────────────

export async function garantirSeedNotas(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;
  const db = getDb();
  const total = await db.notas.count();
  if (total === 0) {
    const notas = gerarNotasIniciais(empresa);
    await db.notas.bulkPut(notas);
  }
  const totalContrapartes = await db.contrapartes.count();
  if (totalContrapartes === 0) {
    await db.contrapartes.bulkPut(CONTRAPARTES_MOCK);
  }
  const totalProdutos = await db.produtos.count();
  if (totalProdutos === 0) {
    await db.produtos.bulkPut(CATALOGO_PRODUTOS);
  }
  localStorage.setItem(flag, "1");
}

// ── listagem / leitura (REAL com fallback local) ─────────────────────────────

async function notasLocais(): Promise<NotaFiscal[]> {
  const db = getDb();
  const lista = await db.notas.toArray();
  return lista.sort((a, b) => b.emitidaEm.localeCompare(a.emitidaEm));
}

export async function listarNotas(): Promise<NotaFiscal[]> {
  let documentos: DocumentoFiscalOut[];
  try {
    documentos = await notasApi.listarDocumentos({ limit: 200 });
  } catch {
    // Sem empresa ativa / backend fora do ar → mantém o app utilizável com o
    // estado local (Dexie). Não propaga erro para não quebrar a tela.
    return notasLocais();
  }

  // Empresa sem documentos no backend → exibe o estado local (seed/rascunhos).
  if (documentos.length === 0) return notasLocais();

  const db = getDb();
  const locais = await db.notas.toArray();
  const porChave = new Map(locais.map((n) => [n.chave, n]));
  const porNumero = new Map(locais.map((n) => [n.numero, n]));

  const mapeadas = documentos.map((doc) => {
    const local =
      (doc.chave ? porChave.get(doc.chave) : undefined) ??
      porNumero.get(doc.numero);
    return mapearDocumento(doc, local);
  });

  return mapeadas.sort((a, b) => b.emitidaEm.localeCompare(a.emitidaEm));
}

export async function obterNota(chave: string): Promise<NotaFiscal | undefined> {
  // A lista já mescla backend+local; reusa-a para manter um único caminho de
  // mapeamento (o detalhe precisa exatamente do mesmo shape da lista).
  const todas = await listarNotas();
  const achada = todas.find((n) => n.chave === chave);
  if (achada) return achada;
  // fallback: leitura local direta (rascunho ainda não listado pelo backend).
  const db = getDb();
  return db.notas.where("chave").equals(chave).first();
}

// ── escrita LOCAL (sem backend equivalente — ver gaps Fase C) ────────────────

/**
 * Persiste a nota. Para nota de SAÍDA de SERVIÇO (itens com ISS, sem ICMS), o
 * caminho REAL é `notas.emitirNfse` (Focus, assíncrono) — disparamos a emissão
 * e anexamos a `focus_ref` retornada à observação para rastreio. Emissão de
 * PRODUTO (NF-e) não tem endpoint no backend: permanece só local. Em qualquer
 * caso o registro local mantém o detalhamento rico (itens, contraparte) que o
 * `DocumentoFiscalOut` não carrega. Falha de emissão NÃO impede o registro
 * local (o app segue utilizável); a `focus_ref` permite reconciliar depois.
 */
export async function salvarNota(nota: NotaFiscal): Promise<void> {
  const db = getDb();

  if (deveEmitirNfse(nota)) {
    try {
      const item = nota.itens[0];
      const out = await notasApi.emitirNfse({
        naturezaOperacao: 1,
        servicoDescricao:
          nota.itens.map((i) => i.descricao).join("; ").slice(0, 2000) ||
          "Prestação de serviço",
        servicoCodigo: item?.cfop ?? "0107", // código municipal: o front não captura — usa CFOP de serviço como placeholder rastreável
        servicoValor: nota.totais.valorNota.toFixed(2),
        aliquotaIss: aliquotaIssNota(nota),
        cnpjTomador:
          nota.contraparte.tipo === "pj" ? nota.contraparte.documento : undefined,
        cpfTomador:
          nota.contraparte.tipo === "pf" ? nota.contraparte.documento : undefined,
        razaoSocialTomador: nota.contraparte.nome || undefined,
        emailTomador: nota.contraparte.email || undefined,
      });
      nota = {
        ...nota,
        protocoloAutorizacao: nota.protocoloAutorizacao ?? out.focusRef,
      };
    } catch {
      // Backend de emissão indisponível / nota não-elegível: segue só local.
      // Gap registrado na Fase C; nenhum fato fiscal é fabricado.
    }
  }

  await db.notas.put(nota);
}

/** Nota de saída de serviço (tem ISS e nenhum ICMS) → elegível a NFS-e real. */
function deveEmitirNfse(nota: NotaFiscal): boolean {
  if (nota.tipo !== "saida") return false;
  const temIss = nota.itens.some((i) => (i.aliquotaIss ?? 0) > 0);
  const temIcms = nota.itens.some((i) => (i.aliquotaIcms ?? 0) > 0);
  return temIss && !temIcms;
}

/** Alíquota ISS predominante da nota, em %, dentro do range válido (2..5). */
function aliquotaIssNota(nota: NotaFiscal): string {
  const aliq = nota.itens.find((i) => (i.aliquotaIss ?? 0) > 0)?.aliquotaIss ?? 0.02;
  // o front guarda alíquota como fração (0.02); o backend espera percentual (2)
  const pct = aliq <= 1 ? aliq * 100 : aliq;
  const clamped = Math.min(5, Math.max(2, pct));
  return clamped.toFixed(4);
}

/**
 * Cancelamento. ⚠️ Sem endpoint no backend (o evento de cancelamento SEFAZ não
 * está exposto). Registrado localmente para refletir a ação na UI. Gap Fase C.
 */
export async function cancelarNota(
  chave: string,
  motivo: string
): Promise<void> {
  const db = getDb();
  const nota = await db.notas.where("chave").equals(chave).first();
  if (!nota) return;
  await db.notas.put({
    ...nota,
    status: "cancelada",
    canceladaEm: new Date().toISOString(),
    motivoCancelamento: motivo,
  });
}

/**
 * Carta de correção (CC-e). ⚠️ Sem endpoint no backend. Local. Gap Fase C.
 */
export async function adicionarCartaCorrecao(
  chave: string,
  texto: string
): Promise<void> {
  const db = getDb();
  const nota = await db.notas.where("chave").equals(chave).first();
  if (!nota) return;
  const cartas = nota.cartasCorrecao ?? [];
  await db.notas.put({
    ...nota,
    cartasCorrecao: [
      ...cartas,
      {
        sequencia: cartas.length + 1,
        texto,
        emitidaEm: new Date().toISOString(),
      },
    ],
  });
}

/**
 * Manifesto de NF-e de entrada. ⚠️ Sem endpoint no backend (MDF-e/manifesto do
 * destinatário não está exposto). Local. Gap Fase C.
 */
export async function manifestarNota(
  chave: string,
  manifesto: StatusManifesto
): Promise<void> {
  const db = getDb();
  const nota = await db.notas.where("chave").equals(chave).first();
  if (!nota) return;
  await db.notas.put({ ...nota, manifesto });
}

// ── catálogo / contrapartes (dado LOCAL de apoio — sem backend) ──────────────

export async function listarContrapartes(): Promise<Contraparte[]> {
  const db = getDb();
  const lista = await db.contrapartes.toArray();
  return lista.length > 0 ? lista : CONTRAPARTES_MOCK;
}

export async function salvarContraparte(c: Contraparte): Promise<void> {
  const db = getDb();
  await db.contrapartes.put(c);
}

export async function listarProdutos(): Promise<ProdutoCatalogo[]> {
  const db = getDb();
  const lista = await db.produtos.toArray();
  return lista.length > 0 ? lista : CATALOGO_PRODUTOS;
}
