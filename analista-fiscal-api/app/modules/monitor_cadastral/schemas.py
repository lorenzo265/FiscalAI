"""Schemas Pydantic — monitor cadastral (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SituacaoRfbIn(StrEnum):
    ATIVA = "ativa"
    SUSPENSA = "suspensa"
    INAPTA = "inapta"
    BAIXADA = "baixada"
    NULA = "nula"


class SituacaoSintegraIn(StrEnum):
    HABILITADA = "habilitada"
    SUSPENSA = "suspensa"
    CANCELADA = "cancelada"
    INAPTA = "inapta"
    BAIXADA = "baixada"
    DESCONHECIDA = "desconhecida"


class RegistrarStatusRfbIn(BaseModel):
    """Snapshot da consulta CNPJ na RFB — vem do sync SERPRO ou input manual."""

    model_config = ConfigDict(extra="forbid")

    consultado_em: datetime
    situacao_cadastral: SituacaoRfbIn
    data_situacao: date | None = None
    motivo_situacao: Annotated[str | None, Field(default=None, max_length=255)]
    restricoes: dict[str, object] | None = None
    regime_apuracao: Annotated[str | None, Field(default=None, max_length=50)]
    snapshot: dict[str, object]


class StatusRfbOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    consultado_em: datetime
    situacao_cadastral: SituacaoRfbIn
    data_situacao: date | None
    motivo_situacao: str | None
    restricoes: dict[str, object] | None
    regime_apuracao: str | None
    snapshot: dict[str, object]
    criado_em: datetime


class RegistrarStatusSintegraIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uf: Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")]
    inscricao_estadual: Annotated[str, Field(min_length=1, max_length=20)]
    consultado_em: datetime
    situacao: SituacaoSintegraIn
    data_situacao: date | None = None
    regime_apuracao_ie: Annotated[str | None, Field(default=None, max_length=60)]
    snapshot: dict[str, object]


class StatusSintegraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    uf: str
    inscricao_estadual: str
    consultado_em: datetime
    situacao: SituacaoSintegraIn
    data_situacao: date | None
    regime_apuracao_ie: str | None
    snapshot: dict[str, object]
    criado_em: datetime
