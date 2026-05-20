from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.shared.types import JsonObject


class MemoriaNodeCreate(BaseModel):
    tipo: str
    rotulo: str
    atributos: JsonObject = {}
    fonte_id: UUID | None = None
    fonte_tipo: str | None = None


class MemoriaNodeOut(BaseModel):
    id: UUID
    tipo: str
    rotulo: str
    atributos: JsonObject
    fonte_id: UUID | None
    fonte_tipo: str | None
    created_at: datetime


class ContextoRAG(BaseModel):
    """Contexto recuperado do grafo para alimentar o LLM."""
    nodes: list[MemoriaNodeOut]
    similaridade_media: float
    query_usada: str
