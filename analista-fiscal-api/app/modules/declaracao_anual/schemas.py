"""Schemas Pydantic — declaração anual SN/MEI (Sprint 6 PR3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TipoDeclaracao(StrEnum):
    DEFIS = "DEFIS"
    DASN_SIMEI = "DASN_SIMEI"


class DeclaracaoStatus(StrEnum):
    GERADA = "gerada"
    TRANSMITIDA = "transmitida"
    ERRO = "erro"


# ── DEFIS — input ────────────────────────────────────────────────────────────


class SocioDefisIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpf: str = Field(min_length=11, max_length=11, pattern=r"^\d{11}$")
    nome: str = Field(min_length=2, max_length=255)
    percentual_capital: Decimal = Field(ge=0, le=100, decimal_places=2)
    rendimentos_isentos: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    rendimentos_tributaveis: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    pro_labore_anual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)


class GerarDefisIn(BaseModel):
    """Dados socioeconômicos informados pelo usuário no momento da geração."""

    model_config = ConfigDict(extra="forbid")

    ano_base: int = Field(ge=2018, le=2099)
    ganho_capital_anual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    lucro_contabil_anual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    estoque_inicial: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    estoque_final: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    saldo_caixa_inicial: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    saldo_caixa_final: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    despesa_total_anual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    isencao_iss_anual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    teve_funcionario: bool = False
    socios: list[SocioDefisIn] = Field(default_factory=list)


# ── DASN-SIMEI — input ───────────────────────────────────────────────────────


class GerarDasnSimeiIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ano_base: int = Field(ge=2018, le=2099)
    receita_comercio_industria: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    receita_servicos: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    teve_empregado: bool = False
    eh_caminhoneiro: bool = False

    @field_validator("ano_base")
    @classmethod
    def _ano_razoavel(cls, v: int) -> int:
        return v


# ── output comum ─────────────────────────────────────────────────────────────


class DeclaracaoAnualOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: TipoDeclaracao
    ano_base: int
    status: DeclaracaoStatus
    protocolo: str | None
    transmitida_em: datetime | None
    receita_bruta_anual: Decimal | None = None
    aviso: str | None = None


class TransmitirOut(BaseModel):
    declaracao_id: UUID
    tipo: TipoDeclaracao
    status: DeclaracaoStatus
    protocolo: str | None
    mensagem: str
    erro: str | None = None
