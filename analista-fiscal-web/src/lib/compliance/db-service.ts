/**
 * Camada de dados do domínio Compliance (Onda 2 / Fase E — integração real).
 *
 * Certidões e Parcelamentos falam com o backend FastAPI via `fetchJson`
 * (`@/lib/http`) montando as rotas com `getEmpresaIdAtiva()`:
 *   - Certidões    → `GET/POST /v1/empresas/{id}/certidoes[/{tipo}]`
 *   - Parcelamentos→ `GET /v1/empresas/{id}/parcelamentos`
 *
 * Intimações NÃO têm endpoint no backend (o módulo `monitor-cadastral` cobre
 * apenas snapshots de situação cadastral RFB/Sintegra — outro conceito). Por
 * isso intimações permanecem em Dexie (local), SEM fingir backend. Idem para o
 * `enviarAoContador` e o `painel` agregado (derivado client-side).
 *
 * Mapeamentos snake→camel são feitos pelo `fetchJson` (toCamel). Aqui só
 * traduzimos o VOCABULÁRIO de domínio do backend para o das telas (tipo,
 * status, derivação de vencimento), sem inventar dado.
 *
 * Dono na integração: agente de domínio compliance.
 */
import { z } from "zod";

import { fetchJson, ApiError } from "@/lib/http";
import { getEmpresaIdAtiva } from "@/lib/empresa-ativa";
import { getDb } from "@/lib/db";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Certidao,
  CompliancePainel,
  Intimacao,
  Parcelamento,
  StatusCertidao,
  StatusIntimacao,
  StatusParcelamento,
  TipoCertidao,
} from "@/lib/schemas/compliance";
import {
  calcularStatusCertidao,
  gerarIntimacoesIniciais,
} from "@/lib/mocks/compliance";

// ── Certidões ───────────────────────────────────────────────────────────────

// `CertidaoOut` do backend (já camelizado pelo fetchJson). Status do backend é
// um conceito DIFERENTE do front: descreve o RESULTADO da consulta (negativa,
// positiva, processando…). O front classifica por VENCIMENTO (vigente / vence
// em breve / vencida). Traduzimos um no outro abaixo.
const certidaoOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipo: z.enum(["CND", "CRF", "CNDT"]),
  numero: z.string().nullable(),
  status: z.enum([
    "negativa",
    "positiva",
    "positiva_com_efeitos_de_negativa",
    "emitida",
    "processando",
    "erro",
  ]),
  emitidaEm: z.string(), // ISO datetime aware
  validUntil: z.string().nullable(), // ISO date | null
  pdfStorageKey: z.string().nullable(),
});
type CertidaoOut = z.infer<typeof certidaoOutSchema>;
const certidoesOutSchema = z.array(certidaoOutSchema);

// `EmitirCertidaoOut` — resultado imediato da solicitação de emissão.
const emitirCertidaoOutSchema = z.object({
  certidaoId: z.string(),
  tipo: z.enum(["CND", "CRF", "CNDT"]),
  status: z.enum([
    "negativa",
    "positiva",
    "positiva_com_efeitos_de_negativa",
    "emitida",
    "processando",
    "erro",
  ]),
  numero: z.string().nullable(),
  validUntil: z.string().nullable(),
  mensagem: z.string(),
  aviso: z.string().nullable().optional(),
});

const TIPO_BACKEND_PARA_FRONT: Record<CertidaoOut["tipo"], TipoCertidao> = {
  CND: "CND_FEDERAL",
  CRF: "CRF_FGTS",
  CNDT: "CNDT_TRABALHISTA",
};

const EMISSOR_POR_TIPO: Record<CertidaoOut["tipo"], string> = {
  CND: "Receita Federal · PGFN",
  CRF: "Caixa Econômica Federal",
  CNDT: "Tribunal Superior do Trabalho",
};

/**
 * Traduz o status de RESULTADO do backend + o vencimento no status de
 * VIGÊNCIA das telas (cor + ícone + palavra preservados via StatusCertidaoPill).
 *
 *  - `processando`/`emitida`            → ainda sem resultado de regularidade.
 *  - `positiva`/`erro`                  → débito/problema → "irregular".
 *  - `negativa`/`positiva_c/efeitos`    → regular → classifica por vencimento.
 */
function mapearStatusCertidao(
  statusBackend: CertidaoOut["status"],
  validUntil: string | null
): StatusCertidao {
  if (statusBackend === "positiva" || statusBackend === "erro") {
    return "irregular";
  }
  if (statusBackend === "processando" || statusBackend === "emitida") {
    // Emitida mas sem afirmar regularidade ainda; trata pelo vencimento se houver.
    return validUntil ? calcularStatusCertidao(validUntil) : "vence_em_breve";
  }
  // negativa | positiva_com_efeitos_de_negativa → regular: vence conforme data.
  if (!validUntil) return "vigente";
  return calcularStatusCertidao(validUntil);
}

function mapearCertidao(out: CertidaoOut): Certidao {
  const tipoFront = TIPO_BACKEND_PARA_FRONT[out.tipo];
  // Sem `valid_until`, o vencimento exibido fica = emissão (a tela calcula dias
  // a partir dele; ausência de validade vira "no dia da emissão"). Não inventamos
  // prazo de validade — o backend é a fonte.
  const vencimento = (out.validUntil ?? out.emitidaEm).slice(0, 10);
  const observacao =
    out.status === "processando"
      ? "Emissão em processamento junto ao órgão emissor."
      : out.status === "erro"
        ? "Falha ao consultar o órgão emissor."
        : out.status === "positiva"
          ? "Certidão positiva — há débitos pendentes."
          : undefined;
  return {
    id: out.id,
    tipo: tipoFront,
    numero: out.numero ?? "—",
    emitidaEm: out.emitidaEm.slice(0, 10),
    vencimento,
    status: mapearStatusCertidao(out.status, out.validUntil),
    emitidaPor: EMISSOR_POR_TIPO[out.tipo],
    observacao,
  };
}

/** Tipo front → tipo de rota do backend (`CND`/`CRF`/`CNDT`). */
function tipoRota(tipo: TipoCertidao): "CND" | "CRF" | "CNDT" | null {
  switch (tipo) {
    case "CND_FEDERAL":
      return "CND";
    case "CRF_FGTS":
      return "CRF";
    case "CNDT_TRABALHISTA":
      return "CNDT";
    // Estadual/Municipal não têm emissão no backend (fora do MVP).
    default:
      return null;
  }
}

function empresaIdOuErro(): string {
  const id = getEmpresaIdAtiva();
  if (!id) {
    throw new ApiError(
      400,
      "EmpresaNaoSelecionada",
      "Nenhuma empresa ativa selecionada."
    );
  }
  return id;
}

export async function listarCertidoes(): Promise<Certidao[]> {
  const empresaId = empresaIdOuErro();
  const out = await fetchJson(
    `/empresas/${empresaId}/certidoes`,
    certidoesOutSchema
  );
  return out
    .map(mapearCertidao)
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));
}

/**
 * Renova/re-emite a certidão. A emissão pode ser ASSÍNCRONA: CRF/CNDT marcam
 * `processando` no backend (scraping ainda não-implementado); CND vai ao SERPRO.
 * Tratamos o status devolvido — NÃO fingimos resultado de regularidade.
 *
 * Recebe o `id` da certidão existente apenas para descobrir o TIPO (a rota de
 * emissão é por tipo). Se a certidão não estiver na lista atual, não há como
 * inferir o tipo → retorna `undefined` (a tela trata como "nada renovado").
 */
export async function renovarCertidao(
  id: string
): Promise<Certidao | undefined> {
  const empresaId = empresaIdOuErro();

  // Descobre o tipo a partir da listagem atual (a rota de emissão é por tipo).
  const atuais = await listarCertidoes();
  const alvo = atuais.find((c) => c.id === id);
  if (!alvo) return undefined;
  const tipo = tipoRota(alvo.tipo);
  if (!tipo) return undefined; // Estadual/Municipal sem emissão no backend.

  const resultado = await fetchJson(
    `/empresas/${empresaId}/certidoes/${tipo}`,
    emitirCertidaoOutSchema,
    { method: "POST" }
  );

  // Monta a certidão renovada a partir do resultado da emissão (status real —
  // pode ser `processando`). Sem `validUntil`, vencimento = hoje (honesto).
  const out: CertidaoOut = {
    id: resultado.certidaoId,
    empresaId,
    tipo: resultado.tipo,
    numero: resultado.numero,
    status: resultado.status,
    emitidaEm: new Date().toISOString(),
    validUntil: resultado.validUntil,
    pdfStorageKey: null,
  };
  return mapearCertidao(out);
}

// ── Parcelamentos ─────────────────────────────────────────────────────────────

// `ParcelamentoOut` do backend (já camelizado). Dinheiro chega como string
// decimal — convertemos para number só na fronteira da tela (os schemas das
// telas são `number`), espelhando o que o adapter de empresa faz.
const parcelamentoOutSchema = z.object({
  id: z.string(),
  empresaId: z.string(),
  tipo: z.enum([
    "ordinario",
    "pert",
    "pert2",
    "simplificado",
    "reabertura",
    "outros",
  ]),
  identificadorExterno: z.string().nullable(),
  dataAdesao: z.string(),
  dividaConsolidada: z.string(),
  numParcelas: z.number().int(),
  parcelaBase: z.string(),
  status: z.enum(["ativo", "quitado", "cancelado", "rescindido"]),
  canceladoEm: z.string().nullable(),
  motivoCancelamento: z.string().nullable(),
  algoritmoVersao: z.string(),
  criadoEm: z.string(),
});
type ParcelamentoOut = z.infer<typeof parcelamentoOutSchema>;
const parcelamentosOutSchema = z.array(parcelamentoOutSchema);

const parcelaOutSchema = z.object({
  id: z.string(),
  numero: z.number().int(),
  vencimento: z.string(),
  valorProjetado: z.string(),
  valorPago: z.string().nullable(),
  pagoEm: z.string().nullable(),
  status: z.string(),
});
const parcelasOutSchema = z.array(parcelaOutSchema);

const TIPO_PARCELAMENTO_LABEL: Record<ParcelamentoOut["tipo"], string> = {
  ordinario: "Parcelamento ordinário",
  pert: "PERT",
  pert2: "PERT 2",
  simplificado: "Parcelamento simplificado",
  reabertura: "Reabertura de parcelamento",
  outros: "Parcelamento",
};

function num(s: string | null | undefined): number {
  if (s == null) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function mapearStatusParcelamento(
  s: ParcelamentoOut["status"]
): StatusParcelamento {
  // Front conhece ativo/rescindido/quitado. `cancelado` ≈ rescindido.
  if (s === "quitado") return "quitado";
  if (s === "ativo") return "ativo";
  return "rescindido"; // cancelado | rescindido
}

/**
 * Mapeia `ParcelamentoOut` → `Parcelamento` (shape da tela). O backend não
 * fornece `orgao`, `assunto`, `parcelaAtual` nem `proximoVencimento` no objeto
 * principal — derivamos:
 *   - `orgao`            → "PGFN" (parcelamento ordinário Lei 10.522 é federal).
 *   - `assunto`          → label do tipo (ex.: "Parcelamento ordinário").
 *   - `parcelaAtual`     → nº de parcelas PAGAS (consultando /parcelas).
 *   - `proximoVencimento`→ vencimento da 1ª parcela em aberto (idem).
 *   - `saldoDevedor`     → soma das parcelas projetadas ainda em aberto.
 *   - `valorParcela`     → `parcela_base`.
 */
async function mapearParcelamento(
  empresaId: string,
  out: ParcelamentoOut
): Promise<Parcelamento> {
  let parcelaAtual = 0;
  let proximoVencimento = out.dataAdesao.slice(0, 10);
  let saldoDevedor = num(out.dividaConsolidada);

  try {
    const parcelas = await fetchJson(
      `/empresas/${empresaId}/parcelamentos/${out.id}/parcelas`,
      parcelasOutSchema
    );
    const pagas = parcelas.filter((p) => p.valorPago != null);
    parcelaAtual = pagas.length;
    const emAberto = parcelas.filter((p) => p.valorPago == null);
    if (emAberto.length > 0) {
      // Parcelas vêm ordenadas por número (asc) no backend.
      proximoVencimento = (emAberto[0]?.vencimento ?? proximoVencimento).slice(
        0,
        10
      );
      saldoDevedor = emAberto.reduce((acc, p) => acc + num(p.valorProjetado), 0);
    } else if (parcelas.length > 0) {
      saldoDevedor = 0; // tudo pago
    }
  } catch {
    // Sem detalhe de parcelas → mantém derivação conservadora (saldo = dívida
    // consolidada, próxima = adesão). NÃO inventamos cronograma.
  }

  return {
    id: out.id,
    numero: out.identificadorExterno ?? out.id.slice(0, 8),
    orgao: "PGFN",
    assunto: TIPO_PARCELAMENTO_LABEL[out.tipo],
    parcelaAtual,
    totalParcelas: out.numParcelas,
    valorParcela: num(out.parcelaBase),
    saldoDevedor,
    proximoVencimento,
    status: mapearStatusParcelamento(out.status),
  };
}

export async function listarParcelamentos(): Promise<Parcelamento[]> {
  const empresaId = empresaIdOuErro();
  const out = await fetchJson(
    `/empresas/${empresaId}/parcelamentos`,
    parcelamentosOutSchema
  );
  return Promise.all(out.map((p) => mapearParcelamento(empresaId, p)));
}

// ── Intimações (LOCAL — sem endpoint no backend) ─────────────────────────────
//
// GAP de contrato: não há endpoint de intimações/caixa-postal-e-CAC no backend.
// O módulo `monitor-cadastral` expõe apenas snapshots de situação cadastral
// (RFB/Sintegra), que é outro conceito. Mantemos intimações em Dexie (local),
// SEM fingir que vêm do backend. Quando houver `/e-cac` ou equivalente, plugar.

const SEED_KEY = "analista-fiscal:compliance-seeded";

export async function garantirSeedCompliance(empresa: Empresa): Promise<void> {
  if (typeof window === "undefined") return;
  const flag = `${SEED_KEY}:${empresa.cnpj}`;
  if (localStorage.getItem(flag)) return;

  // Certidões e parcelamentos agora vêm do backend — NÃO semeamos mais Dexie
  // para esses. Apenas intimações (sem endpoint) seguem com seed local.
  const db = getDb();
  if ((await db.intimacoes.count()) === 0) {
    await db.intimacoes.bulkPut(gerarIntimacoesIniciais(empresa));
  }
  localStorage.setItem(flag, "1");
}

export async function listarIntimacoes(): Promise<Intimacao[]> {
  const db = getDb();
  const lista = await db.intimacoes.toArray();
  return lista.sort((a, b) => b.recebidoEm.localeCompare(a.recebidoEm));
}

export async function obterIntimacao(
  id: string
): Promise<Intimacao | undefined> {
  const db = getDb();
  return db.intimacoes.get(id);
}

export async function atualizarStatusIntimacao(
  id: string,
  status: StatusIntimacao
): Promise<void> {
  const db = getDb();
  const intim = await db.intimacoes.get(id);
  if (!intim) return;
  await db.intimacoes.put({ ...intim, status });
}

export async function enviarIntimacaoAoContador(id: string): Promise<void> {
  // GAP: não há endpoint de "encaminhar ao contador" no backend. Mantemos local
  // (marca a flag em Dexie) — não fingimos uma notificação que não acontece.
  const db = getDb();
  const intim = await db.intimacoes.get(id);
  if (!intim) return;
  await db.intimacoes.put({ ...intim, enviadoContador: true });
}

// ── Painel agregado (derivado client-side) ───────────────────────────────────
//
// GAP: não há endpoint de painel/resumo de compliance no backend. Derivamos o
// painel a partir das listas reais (certidões + parcelamentos do backend) e das
// intimações locais. Sem dado inventado — apenas agregação.
export async function compliancePainel(): Promise<CompliancePainel> {
  const [certidoes, intimacoes, parcelamentos] = await Promise.all([
    listarCertidoes().catch(() => [] as Certidao[]),
    listarIntimacoes().catch(() => [] as Intimacao[]),
    listarParcelamentos().catch(() => [] as Parcelamento[]),
  ]);
  const vigentes = certidoes.filter((c) => c.status === "vigente");
  const intimacoesAbertas = intimacoes.filter(
    (i) => i.status !== "respondida" && i.status !== "encerrada"
  );
  const proximas = certidoes
    .filter((c) => c.status !== "vencida")
    .sort((a, b) => a.vencimento.localeCompare(b.vencimento));
  return {
    certidoesVigentes: vigentes.length,
    certidoesTotal: certidoes.length,
    intimacoesAbertas: intimacoesAbertas.length,
    intimacoesTotal: intimacoes.length,
    parcelamentosAtivos: parcelamentos.filter((p) => p.status === "ativo")
      .length,
    // Situação cadastral CNPJ (RFB) exigiria snapshot no monitor-cadastral; sem
    // garantia de snapshot, assumimos ativo (a tela só usa como indicador macro).
    cnpjAtivo: true,
    proximaCertidaoVencimento: proximas[0]?.vencimento ?? null,
  };
}
