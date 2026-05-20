"""Schemas Pydantic — EFD-Reinf (Sprint 11 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RegimeTomadorIn(StrEnum):
    SIMPLES_NACIONAL = "simples_nacional"
    MEI = "mei"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"


class TipoEventoReinfIn(StrEnum):
    R_2010 = "R-2010"
    R_4020 = "R-4020"
    R_9000 = "R-9000"


class RegistrarRetencaoIn(BaseModel):
    """Registra uma retenção R-4020 (pagamento PJ→PJ) com cálculo automático.

    ``referencia_id`` (UUID) identifica univocamente o pagamento — pode vir
    da fatura, NF de serviço ou movimento bancário. Default: novo UUID
    (caller pode passar o próprio para idempotência cross-system).
    """

    model_config = ConfigDict(extra="forbid")

    referencia_id: Annotated[UUID, Field(default_factory=uuid4)]
    cnpj_prestador: Annotated[str, Field(min_length=14, max_length=14, pattern=r"^\d{14}$")]
    razao_social_prestador: Annotated[str, Field(min_length=3, max_length=255)]
    valor_servico: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    competencia: date
    descricao_servico: Annotated[str | None, Field(default=None, max_length=255)]


class EventoReinfOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo_evento: TipoEventoReinfIn
    referencia_tipo: str
    referencia_id: UUID
    periodo_apuracao: date
    valor_bruto_servico: Decimal
    ir_retido: Decimal
    pis_retido: Decimal
    cofins_retido: Decimal
    csll_retido: Decimal
    payload: dict[str, object]
    status: str
    algoritmo_versao: str
    criado_em: datetime
    transmitido_em: datetime | None
