"""Schemas Pydantic — parcelamentos (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoParcelamentoIn(StrEnum):
    ORDINARIO = "ordinario"
    PERT = "pert"
    PERT2 = "pert2"
    SIMPLIFICADO = "simplificado"
    REABERTURA = "reabertura"
    OUTROS = "outros"


class StatusParcelamentoIn(StrEnum):
    ATIVO = "ativo"
    QUITADO = "quitado"
    CANCELADO = "cancelado"
    RESCINDIDO = "rescindido"


class TipoContribuinteIn(StrEnum):
    PJ = "pj"
    PF = "pf"


class CriarParcelamentoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoParcelamentoIn = TipoParcelamentoIn.ORDINARIO
    identificador_externo: Annotated[str | None, Field(default=None, max_length=80)]
    data_adesao: date
    divida_consolidada: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    num_parcelas: Annotated[int, Field(ge=1, le=240)]
    contribuinte: TipoContribuinteIn = TipoContribuinteIn.PJ


class ParcelaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero: int
    vencimento: date
    valor_projetado: Decimal
    valor_pago: Decimal | None
    pago_em: date | None
    status: str


class ParcelamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: TipoParcelamentoIn
    identificador_externo: str | None
    data_adesao: date
    divida_consolidada: Decimal
    num_parcelas: int
    parcela_base: Decimal
    status: StatusParcelamentoIn
    cancelado_em: datetime | None
    motivo_cancelamento: str | None
    algoritmo_versao: str
    criado_em: datetime


class CancelarParcelamentoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: Annotated[str, Field(min_length=3, max_length=255)]
