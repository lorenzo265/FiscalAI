"""Schemas Pydantic — contábil (Sprint 9 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NaturezaConta(StrEnum):
    DEBITO = "D"
    CREDITO = "C"


class TipoConta(StrEnum):
    ATIVO = "ativo"
    PASSIVO = "passivo"
    PATRIMONIO_LIQUIDO = "patrimonio_liquido"
    RECEITA = "receita"
    DESPESA = "despesa"
    CONTA_RESULTADO = "conta_resultado"


class StatusLancamento(StrEnum):
    RASCUNHO = "rascunho"
    CONFIRMADO = "confirmado"
    ENCERRADO = "encerrado"


class OrigemLancamento(StrEnum):
    MANUAL = "manual"
    NFE = "nfe"
    TRANSACAO = "transacao"
    DEPRECIACAO = "depreciacao"
    PROVISAO = "provisao"
    ENCERRAMENTO = "encerramento"
    AJUSTE = "ajuste"


# ── Plano de contas ─────────────────────────────────────────────────────────


class CriarContaIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    codigo: str = Field(min_length=1, max_length=20, pattern=r"^[0-9\.]+$")
    descricao: str = Field(min_length=2, max_length=255)
    parent_id: UUID | None = None
    natureza: NaturezaConta
    tipo: TipoConta
    nivel: int = Field(ge=1, le=8)
    aceita_lancamento: bool = False
    codigo_ecd_referencial: str | None = Field(default=None, max_length=20)
    valid_from: date


class ContaContabilOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    descricao: str
    parent_id: UUID | None
    natureza: NaturezaConta
    tipo: TipoConta
    nivel: int
    aceita_lancamento: bool
    codigo_ecd_referencial: str | None
    valid_from: date
    valid_to: date | None


class ClonarPlanoOut(BaseModel):
    contas_criadas: int
    contas_existentes: int
    primeira_competencia: date


# ── Lançamentos ─────────────────────────────────────────────────────────────


class PartidaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conta_id: UUID
    tipo: NaturezaConta  # 'D' ou 'C'
    valor: Decimal = Field(gt=0, decimal_places=2)


class CriarLancamentoIn(BaseModel):
    """Lançamento manual com 2+ partidas em partidas dobradas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    data_lancamento: date
    competencia: date
    historico: str = Field(min_length=3, max_length=500)
    partidas: list[PartidaIn] = Field(min_length=2)


class PartidaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conta_contabil_id: UUID
    tipo: NaturezaConta
    valor: Decimal
    ordem: int


class LancamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    data_lancamento: date
    competencia: date
    historico: str
    origem_tipo: OrigemLancamento
    origem_id: UUID | None
    total_debito: Decimal
    total_credito: Decimal
    status: StatusLancamento
    criado_em: datetime
    partidas: list[PartidaOut] = Field(default_factory=list)


# ── Motor automático (PR2) ──────────────────────────────────────────────────


class TipoFatoAuto(StrEnum):
    NFE = "nfe"
    TRANSACAO = "transacao"
    DEPRECIACAO = "depreciacao"
    PROVISAO = "provisao"


class LoteAutoOut(BaseModel):
    """Resultado do lote do motor automático."""

    tipo: TipoFatoAuto
    competencia: date
    fatos_avaliados: int
    lancamentos_criados: int
    lancamentos_existentes: int
    fatos_pulados: int
    algoritmo_versao: str


# ── Relatórios (PR3) ────────────────────────────────────────────────────────


class LinhaBalanceteOut(BaseModel):
    conta_id: UUID
    codigo: str
    descricao: str
    natureza: NaturezaConta
    tipo: TipoConta
    nivel: int
    saldo_inicial: Decimal
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_final: Decimal


class BalanceteOut(BaseModel):
    competencia: date
    linhas: list[LinhaBalanceteOut]
    total_debitos: Decimal
    total_creditos: Decimal


class LinhaRazaoOut(BaseModel):
    lancamento_id: UUID
    data_lancamento: date
    historico: str
    debito: Decimal
    credito: Decimal
    saldo_corrente: Decimal


class RazaoOut(BaseModel):
    conta_id: UUID
    conta_codigo: str
    conta_descricao: str
    competencia: date
    saldo_inicial: Decimal
    saldo_final: Decimal
    linhas: list[LinhaRazaoOut]


class EncerramentoMensalOut(BaseModel):
    competencia: date
    saldos_persistidos: int
    lancamentos_encerrados: int


class EncerramentoAnualOut(BaseModel):
    ano: int
    receitas_zeradas: Decimal
    despesas_zeradas: Decimal
    resultado_exercicio: Decimal
    lancamento_apuracao_id: UUID
