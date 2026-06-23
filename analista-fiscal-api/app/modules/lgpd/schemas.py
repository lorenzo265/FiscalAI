"""Schemas Pydantic v2 do modulo LGPD (Marco 3)."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import JsonObject


class ExportacaoLgpdOut(BaseModel):
    """Pacote de portabilidade (LGPD art. 18, II) -- todos os dados do tenant."""

    gerado_em: str
    tenant_id: UUID
    resumo: dict[str, int]
    dados: JsonObject


class ConfirmacaoExclusaoIn(BaseModel):
    """Corpo da exclusao -- exige confirmacao explicita (acao destrutiva)."""

    model_config = ConfigDict(extra="forbid")

    confirmar: Literal[True] = Field(
        ..., description="Deve ser `true` -- confirma o pedido de esquecimento."
    )


class ExclusaoLgpdOut(BaseModel):
    """Recibo do esquecimento por anonimizacao (LGPD art. 18, VI)."""

    status: str
    anonimizado_em: str
    expurgo_apos: str
    resumo: dict[str, int]
