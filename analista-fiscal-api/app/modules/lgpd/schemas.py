"""Schemas Pydantic v2 do modulo LGPD (Marco 3)."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.shared.types import JsonObject


class ExportacaoLgpdOut(BaseModel):
    """Pacote de portabilidade (LGPD art. 18, II) -- todos os dados do tenant."""

    gerado_em: str
    tenant_id: UUID
    resumo: dict[str, int]
    dados: JsonObject
