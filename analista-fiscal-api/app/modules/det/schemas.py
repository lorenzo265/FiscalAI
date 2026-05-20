"""Schemas Pydantic — DET (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RegistrarMensagemDetIn(BaseModel):
    """Registro manual de mensagem DET — origem: API SERPRO ou inserção manual.

    Idempotente por (empresa, id_externo_det). Classificador LLM (LLM cloud)
    posterior preenche tipo/prioridade/prazo via outro endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    id_externo_det: Annotated[str, Field(min_length=1, max_length=80)]
    assunto: Annotated[str, Field(min_length=1, max_length=255)]
    corpo: Annotated[str | None, Field(default=None)]
    origem: Annotated[str, Field(default="MTE", max_length=50)]
    recebida_em: datetime


class MensagemDetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    id_externo_det: str
    assunto: str
    corpo: str | None
    origem: str
    recebida_em: datetime
    lida_em: datetime | None
    tipo: str | None
    prioridade: str | None
    prazo_resposta: date | None
    encaminhada_marketplace: bool
    criado_em: datetime
