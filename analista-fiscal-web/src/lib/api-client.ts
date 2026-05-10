import { z } from "zod";
import {
  cnpjLookupResponseSchema,
  type CnpjLookupResponse,
} from "@/lib/schemas/cnpj-lookup";
import {
  apuracaoFiscalSchema,
  fiscalHealthSchema,
  historicoFiscalSchema,
  type ApuracaoFiscal,
  type FiscalHealth,
  type HistoricoMes,
} from "@/lib/schemas/fiscal";
import { eventosAgendaSchema, type EventoAgenda } from "@/lib/schemas/agenda";
import { guiasDASSchema, type GuiaDAS } from "@/lib/schemas/guias";
import {
  contraparteSchema,
  produtoCatalogoSchema,
  type Contraparte,
  type ProdutoCatalogo,
} from "@/lib/schemas/nota";
import type { Empresa } from "@/lib/schemas/empresa";
import {
  conciliarTransacao,
  conectarNovaConta,
  listarContasBancarias,
  listarContasPagarReceber,
  listarTodasTransacoes,
  listarTransacoes,
  marcarContaPaga,
  obterContaBancaria,
  removerContaPagarReceber,
  sincronizarConta,
  adicionarContaPagarReceber,
  atualizarContaPagarReceber,
  atualizarStatusVencidos,
} from "@/lib/controles/db-service";
import { gerarFluxoCaixa } from "@/lib/mocks/controles";
import type {
  ContaBancaria,
  ContaPagarReceber,
  FluxoCaixa,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import {
  adicionarEventoEsocial,
  adicionarFuncionario,
  atualizarStatusEvento,
  gerarHoleritesDoMes,
  listarEventosEsocial,
  listarFuncionarios,
  listarHolerites,
  listarHoleritesDoMes,
  obterFuncionario,
  transmitirEventosDoMes,
} from "@/lib/pessoal/db-service";
import { listarLancamentos } from "@/lib/contabil/db-service";
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
import {
  enviarPergunta as enviarPerguntaService,
  limparMensagens,
  listarMensagens,
} from "@/lib/assistente/db-service";
import type { MensagemAssistente } from "@/lib/schemas/assistente";
import { mockLatency } from "@/lib/mocks/utils";
import type {
  Certidao,
  CompliancePainel,
  Intimacao,
  Parcelamento,
  StatusIntimacao,
} from "@/lib/schemas/compliance";
import {
  gerarBalanco,
  gerarDFC,
  gerarDreComparativo,
  gerarIndicadores,
} from "@/lib/relatorios/geracao";
import type {
  BalancoPatrimonial,
  DFC,
  DreComparativo,
  Indicador,
} from "@/lib/schemas/relatorios";
import type {
  EventoEsocial,
  Funcionario,
  Holerite,
  StatusEventoEsocial,
} from "@/lib/schemas/pessoal";

const BASE = "/api/mock";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJson<T>(
  path: string,
  schema: z.ZodSchema<T>,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, "invalid_json");
  }
  if (!res.ok) {
    const errMsg =
      (parsed as { error?: string } | null)?.error ?? `http_${res.status}`;
    throw new ApiError(res.status, errMsg);
  }
  return schema.parse(parsed);
}

function querystringDe(empresa: Empresa | null | undefined): string {
  if (!empresa) return "";
  const sp = new URLSearchParams({
    cnpj: empresa.cnpj,
    razao: empresa.razaoSocial,
    regime: empresa.regime,
    fat12: String(empresa.faturamento12m),
    uf: empresa.uf,
  });
  if (empresa.anexoSimples) sp.set("anexo", empresa.anexoSimples);
  return `?${sp.toString()}`;
}

export const api = {
  empresa: {
    lookupCnpj: (cnpj: string): Promise<CnpjLookupResponse> =>
      fetchJson("/empresa/cnpj-lookup", cnpjLookupResponseSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cnpj }),
      }),
  },
  fiscal: {
    saude: (empresa: Empresa | null): Promise<FiscalHealth> =>
      fetchJson(`/fiscal/saude${querystringDe(empresa)}`, fiscalHealthSchema),
    apuracaoAtual: (empresa: Empresa | null): Promise<ApuracaoFiscal> =>
      fetchJson(
        `/fiscal/apuracao/atual${querystringDe(empresa)}`,
        apuracaoFiscalSchema
      ),
    historico: (empresa: Empresa | null, meses = 6): Promise<HistoricoMes[]> => {
      const sep = querystringDe(empresa) ? "&" : "?";
      return fetchJson(
        `/fiscal/historico${querystringDe(empresa)}${sep}meses=${meses}`,
        historicoFiscalSchema
      );
    },
    guias: (empresa: Empresa | null): Promise<GuiaDAS[]> =>
      fetchJson(`/fiscal/guias${querystringDe(empresa)}`, guiasDASSchema),
  },
  agenda: {
    listar: (empresa: Empresa | null): Promise<EventoAgenda[]> =>
      fetchJson(`/agenda${querystringDe(empresa)}`, eventosAgendaSchema),
    listarMes: (
      empresa: Empresa | null,
      ano: number,
      mes: number
    ): Promise<EventoAgenda[]> => {
      const sep = querystringDe(empresa) ? "&" : "?";
      return fetchJson(
        `/agenda${querystringDe(empresa)}${sep}ano=${ano}&mes=${mes}`,
        eventosAgendaSchema
      );
    },
    listarAno: (empresa: Empresa | null, ano: number): Promise<EventoAgenda[]> => {
      const sep = querystringDe(empresa) ? "&" : "?";
      return fetchJson(
        `/agenda${querystringDe(empresa)}${sep}modo=ano&ano=${ano}`,
        eventosAgendaSchema
      );
    },
  },
  notas: {
    catalogo: (): Promise<ProdutoCatalogo[]> =>
      fetchJson("/notas/catalogo", z.array(produtoCatalogoSchema)),
    lookupContraparte: (documento: string): Promise<Contraparte> =>
      fetchJson("/notas/contraparte-lookup", contraparteSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ documento }),
      }),
  },
  controles: {
    listarBancos: (): Promise<ContaBancaria[]> => listarContasBancarias(),
    obterBanco: (id: string): Promise<ContaBancaria | undefined> =>
      obterContaBancaria(id),
    sincronizarBanco: (id: string): Promise<ContaBancaria | undefined> =>
      sincronizarConta(id),
    conectarBanco: (empresa: Empresa, bancoId: string): Promise<ContaBancaria> =>
      conectarNovaConta(empresa, bancoId),
    listarTransacoes: (contaId: string): Promise<TransacaoBancaria[]> =>
      listarTransacoes(contaId),
    listarTodasTransacoes: (): Promise<TransacaoBancaria[]> =>
      listarTodasTransacoes(),
    conciliarTransacao: (
      transacaoId: string,
      lancamentoId: string | null
    ): Promise<void> => conciliarTransacao(transacaoId, lancamentoId),
    listarContasPagarReceber: async (): Promise<ContaPagarReceber[]> => {
      await atualizarStatusVencidos();
      return listarContasPagarReceber();
    },
    adicionarContaPagarReceber: (conta: ContaPagarReceber): Promise<void> =>
      adicionarContaPagarReceber(conta),
    atualizarContaPagarReceber: (conta: ContaPagarReceber): Promise<void> =>
      atualizarContaPagarReceber(conta),
    removerContaPagarReceber: (id: string): Promise<void> =>
      removerContaPagarReceber(id),
    marcarContaPaga: (id: string, pagoEm: string): Promise<void> =>
      marcarContaPaga(id, pagoEm),
    fluxoCaixa: async (dias = 90): Promise<FluxoCaixa> => {
      await atualizarStatusVencidos();
      const [contas, contasPR, transacoes] = await Promise.all([
        listarContasBancarias(),
        listarContasPagarReceber(),
        listarTodasTransacoes(),
      ]);
      const saldoHoje = contas.reduce((acc, c) => acc + c.saldo, 0);
      return gerarFluxoCaixa(
        { saldoHoje, contas: contasPR, transacoes },
        dias
      );
    },
  },
  pessoal: {
    listarFuncionarios: (): Promise<Funcionario[]> => listarFuncionarios(),
    obterFuncionario: (id: string): Promise<Funcionario | undefined> =>
      obterFuncionario(id),
    adicionarFuncionario: (f: Funcionario): Promise<void> =>
      adicionarFuncionario(f),
    listarHolerites: (): Promise<Holerite[]> => listarHolerites(),
    listarHoleritesDoMes: (
      ano: number,
      mes: number
    ): Promise<Holerite[]> => listarHoleritesDoMes(ano, mes),
    gerarHoleritesDoMes: (ano: number, mes: number): Promise<Holerite[]> =>
      gerarHoleritesDoMes(ano, mes),
    listarEventosEsocial: (): Promise<EventoEsocial[]> => listarEventosEsocial(),
    adicionarEventoEsocial: (evento: EventoEsocial): Promise<void> =>
      adicionarEventoEsocial(evento),
    atualizarStatusEvento: (
      id: string,
      status: StatusEventoEsocial,
      extras?: { recibo?: string; motivoErro?: string }
    ): Promise<void> => atualizarStatusEvento(id, status, extras),
    transmitirEventosDoMes: (
      ano: number,
      mes: number
    ): Promise<{ transmitidos: number }> =>
      transmitirEventosDoMes(ano, mes),
  },
  assistente: {
    listarMensagens: (): Promise<MensagemAssistente[]> => listarMensagens(),
    enviarPergunta: async (
      empresa: Empresa,
      pergunta: string
    ): Promise<{
      pergunta: MensagemAssistente;
      resposta: MensagemAssistente;
    }> => {
      await mockLatency(800, 1500);
      return enviarPerguntaService(empresa, pergunta);
    },
    limparHistorico: (): Promise<void> => limparMensagens(),
  },
  compliance: {
    painel: (): Promise<CompliancePainel> => compliancePainel(),
    listarCertidoes: (): Promise<Certidao[]> => listarCertidoes(),
    renovarCertidao: async (id: string): Promise<Certidao | undefined> => {
      await mockLatency(900, 1500);
      return renovarCertidao(id);
    },
    listarIntimacoes: (): Promise<Intimacao[]> => listarIntimacoes(),
    obterIntimacao: (id: string): Promise<Intimacao | undefined> =>
      obterIntimacao(id),
    marcarIntimacaoLida: (id: string): Promise<void> =>
      atualizarStatusIntimacao(id, "lida"),
    atualizarStatusIntimacao: (
      id: string,
      status: StatusIntimacao
    ): Promise<void> => atualizarStatusIntimacao(id, status),
    enviarAoContador: async (id: string): Promise<void> => {
      await mockLatency(700, 1100);
      return enviarIntimacaoAoContador(id);
    },
    listarParcelamentos: (): Promise<Parcelamento[]> => listarParcelamentos(),
  },
  relatorios: {
    dre: async (): Promise<DreComparativo> => {
      const lancamentos = await listarLancamentos();
      return gerarDreComparativo(lancamentos);
    },
    balanco: async (): Promise<BalancoPatrimonial> => {
      const lancamentos = await listarLancamentos();
      return gerarBalanco(lancamentos);
    },
    dfc: async (): Promise<DFC> => {
      const lancamentos = await listarLancamentos();
      return gerarDFC(lancamentos);
    },
    indicadores: async (): Promise<Indicador[]> => {
      const [lancamentos, contasPagarReceber, holerites] = await Promise.all([
        listarLancamentos(),
        listarContasPagarReceber(),
        listarHolerites(),
      ]);
      return gerarIndicadores({ lancamentos, contasPagarReceber, holerites });
    },
  },
};
