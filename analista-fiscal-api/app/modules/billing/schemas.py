"""Schemas Pydantic v2 do billing (Marco 2)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanoOut(BaseModel):
    """Plano do catálogo (resposta de GET /planos)."""

    codigo: str
    nome: str
    preco_mensal: Decimal
    descricao: str
    max_empresas: int


class IniciarAssinaturaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plano_codigo: str = Field(
        ..., description="Código do plano: essencial | profissional | avancado."
    )


class AssinaturaOut(BaseModel):
    id: UUID
    plano_codigo: str
    status: str
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    checkout_url: str | None = None
