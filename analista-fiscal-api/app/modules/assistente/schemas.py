from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.marketplace.schemas import ParceiroSugeridoOut


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
    # Sprint 13 PR2 — quando ``encaminhar_marketplace=True``, o assistente
    # popula até 3 parceiros sugeridos para o cliente escolher. Lista vazia
    # quando não há parceiros aptos (cliente vê mensagem mas sem opções).
    categoria_marketplace_sugerida: str | None = None
    parceiros_sugeridos: list[ParceiroSugeridoOut] = Field(default_factory=list)
    provider_usado: str
    tokens_input: int
    tokens_output: int
    tokens_cached: int
    custo_usd: Decimal
    latencia_ms: int
    empresa_id: UUID
