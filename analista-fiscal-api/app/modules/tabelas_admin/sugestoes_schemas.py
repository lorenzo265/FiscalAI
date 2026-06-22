"""Schemas de sugestões de vigência (Sprint 19.5 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import JsonObject

StatusSugestao = Literal["pendente", "aprovada", "rejeitada", "expirada"]


class SugestaoVigenciaOut(BaseModel):
    """Detalhe da sugestão devolvido pelos endpoints GET."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo_tabela: str
    valid_from: date
    payload_jsonb: JsonObject
    fonte_norma: str
    fonte_dou_url: str | None
    fonte_dou_pagina: int | None
    llm_modelo: str
    llm_versao_prompt: str
    llm_confianca: Decimal
    recheck_passou: bool
    recheck_observacoes: JsonObject
    status: StatusSugestao
    aprovada_em: datetime | None
    aprovada_por_usuario_id: UUID | None
    rejeitada_motivo: str | None
    vigencia_tabela_log_id: UUID | None
    idempotency_key: UUID
    criado_em: datetime


class RejeitarSugestaoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=3, max_length=500)


__all__ = ["RejeitarSugestaoIn", "StatusSugestao", "SugestaoVigenciaOut"]
