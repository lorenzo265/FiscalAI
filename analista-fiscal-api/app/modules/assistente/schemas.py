from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=3, max_length=2000)
    contexto_adicional: str | None = Field(default=None, max_length=500)
    contem_pii: bool = False  # True → roteamento obrigatório para Ollama local


class CitacaoOut(BaseModel):
    fato_id: str
    trecho_citado: str


class RespostaOut(BaseModel):
    resposta: str
    citacoes: list[CitacaoOut]
    encaminhar_marketplace: bool
    categoria_marketplace: str | None
    provider_usado: str
    tokens_input: int
    tokens_output: int
    tokens_cached: int
    custo_usd: Decimal
    latencia_ms: int
    empresa_id: UUID
