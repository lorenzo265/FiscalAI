"""Schemas Pydantic — conciliação banco × NF (Sprint 7 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoMatch(StrEnum):
    AUTO = "AUTO"
    SUGERIDA = "SUGERIDA"
    MANUAL = "MANUAL"
    REJEITADA = "REJEITADA"


class RunConciliacaoIn(BaseModel):
    """Janela de busca para o run. Defaults cobrem 90 dias."""

    model_config = ConfigDict(extra="forbid")

    desde: date | None = Field(default=None, description="Data inicial (AAAA-MM-DD)")
    ate: date | None = Field(default=None, description="Data final inclusiva")


class RunConciliacaoOut(BaseModel):
    """Resultado do run."""

    transacoes_avaliadas: int
    documentos_candidatos: int
    matches_auto: int
    matches_sugeridos: int
    pares_avaliados: int
    algoritmo_versao: str


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transacao_id: UUID
    documento_fiscal_id: UUID
    confianca: int
    tipo: TipoMatch
    algoritmo_versao: str
    score_breakdown: list[str] = Field(default_factory=list)
    criado_em: datetime
    confirmado_em: datetime | None = None
    rejeitado_em: datetime | None = None
    # Campos auxiliares para UI (vêm de joins quando disponíveis)
    transacao_valor: Decimal | None = None
    transacao_data: date | None = None
    documento_valor: Decimal | None = None
    documento_data: date | None = None
