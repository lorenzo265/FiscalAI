import Dexie, { type Table } from "dexie";
import type { Empresa } from "@/lib/schemas/empresa";
import type {
  Contraparte,
  NotaFiscal,
  ProdutoCatalogo,
} from "@/lib/schemas/nota";
import type { LancamentoContabil } from "@/lib/schemas/contabil";
import type {
  ContaBancaria,
  ContaPagarReceber,
  TransacaoBancaria,
} from "@/lib/schemas/controles";
import type {
  EventoEsocial,
  Funcionario,
  Holerite,
} from "@/lib/schemas/pessoal";
import type {
  Certidao,
  Intimacao,
  Parcelamento,
} from "@/lib/schemas/compliance";
import type { MensagemAssistente } from "@/lib/schemas/assistente";

export class AnalistaFiscalDB extends Dexie {
  empresas!: Table<Empresa, string>;
  notas!: Table<NotaFiscal, string>;
  contrapartes!: Table<Contraparte, string>;
  produtos!: Table<ProdutoCatalogo, string>;
  lancamentos!: Table<LancamentoContabil, string>;
  contasBancarias!: Table<ContaBancaria, string>;
  transacoes!: Table<TransacaoBancaria, string>;
  contasPagarReceber!: Table<ContaPagarReceber, string>;
  funcionarios!: Table<Funcionario, string>;
  holerites!: Table<Holerite, string>;
  eventosEsocial!: Table<EventoEsocial, string>;
  certidoes!: Table<Certidao, string>;
  intimacoes!: Table<Intimacao, string>;
  parcelamentos!: Table<Parcelamento, string>;
  mensagensAssistente!: Table<MensagemAssistente, string>;

  constructor() {
    super("AnalistaFiscalDB");
    this.version(1).stores({
      empresas: "id, cnpj, regime",
    });
    this.version(2).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
    });
    this.version(3).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
      lancamentos: "id, data, contaDebito, contaCredito, origem",
    });
    this.version(4).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
      lancamentos: "id, data, contaDebito, contaCredito, origem",
      contasBancarias: "id, bancoId, conectadaEm",
      transacoes: "id, contaId, [contaId+data], data, categoria, conciliada",
      contasPagarReceber: "id, tipo, status, vencimento, [tipo+status]",
    });
    this.version(5).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
      lancamentos: "id, data, contaDebito, contaCredito, origem",
      contasBancarias: "id, bancoId, conectadaEm",
      transacoes: "id, contaId, [contaId+data], data, categoria, conciliada",
      contasPagarReceber: "id, tipo, status, vencimento, [tipo+status]",
      funcionarios: "id, cpf, status, dataAdmissao",
      holerites:
        "id, funcionarioId, [funcionarioId+ano+mes], competencia, status",
      eventosEsocial: "id, tipo, status, competencia, criadoEm",
    });
    this.version(6).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
      lancamentos: "id, data, contaDebito, contaCredito, origem",
      contasBancarias: "id, bancoId, conectadaEm",
      transacoes: "id, contaId, [contaId+data], data, categoria, conciliada",
      contasPagarReceber: "id, tipo, status, vencimento, [tipo+status]",
      funcionarios: "id, cpf, status, dataAdmissao",
      holerites:
        "id, funcionarioId, [funcionarioId+ano+mes], competencia, status",
      eventosEsocial: "id, tipo, status, competencia, criadoEm",
      certidoes: "id, tipo, status, vencimento",
      intimacoes: "id, status, recebidoEm, orgao",
      parcelamentos: "id, status, proximoVencimento",
    });
    this.version(7).stores({
      empresas: "id, cnpj, regime",
      notas: "id, chave, tipo, status, emitidaEm",
      contrapartes: "id, documento, tipo",
      produtos: "id, descricao, tipo",
      lancamentos: "id, data, contaDebito, contaCredito, origem",
      contasBancarias: "id, bancoId, conectadaEm",
      transacoes: "id, contaId, [contaId+data], data, categoria, conciliada",
      contasPagarReceber: "id, tipo, status, vencimento, [tipo+status]",
      funcionarios: "id, cpf, status, dataAdmissao",
      holerites:
        "id, funcionarioId, [funcionarioId+ano+mes], competencia, status",
      eventosEsocial: "id, tipo, status, competencia, criadoEm",
      certidoes: "id, tipo, status, vencimento",
      intimacoes: "id, status, recebidoEm, orgao",
      parcelamentos: "id, status, proximoVencimento",
      mensagensAssistente: "id, role, criadoEm",
    });
  }
}

let _db: AnalistaFiscalDB | null = null;

export function getDb(): AnalistaFiscalDB {
  if (typeof window === "undefined") {
    throw new Error("Dexie só está disponível no client.");
  }
  if (!_db) _db = new AnalistaFiscalDB();
  return _db;
}
