"""Schemas Pydantic do módulo e-CAC (Sprint 6 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TipoMensagem(StrEnum):
    INTIMACAO = "intimacao"
    AVISO = "aviso"
    INFORMATIVA = "informativa"
    OUTRO = "outro"


class Prioridade(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class MensagemOut(BaseModel):
    """Item da listagem de mensagens e-CAC."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    assunto: str
    recebida_em: datetime
    lida_em: datetime | None
    tipo: TipoMensagem | None
    prioridade: Prioridade | None
    prazo_resposta: date | None
    encaminhada_marketplace: bool


class SyncResultadoOut(BaseModel):
    """Resultado de uma sincronização da caixa postal."""

    novas: int
    classificadas: int
    total_no_lote: int
    aviso: str | None = None
