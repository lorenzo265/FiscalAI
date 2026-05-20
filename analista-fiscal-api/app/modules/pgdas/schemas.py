"""Schemas Pydantic da transmissão PGDAS-D (Sprint 6 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransmissaoStatus(StrEnum):
    PENDENTE = "pendente"
    TRANSMITIDA = "transmitida"
    ERRO = "erro"
    RETIFICADA = "retificada"


class TransmitirPgdasIn(BaseModel):
    """Pedido de transmissão. Empresa, competência e flag de retificação."""

    model_config = ConfigDict(extra="forbid")

    eh_retificadora: bool = Field(
        default=False,
        description=(
            "True para gerar uma declaração retificadora (substitui a anterior "
            "no SERPRO). Requer transmissão prévia bem-sucedida."
        ),
    )


class TransmitirPgdasOut(BaseModel):
    """Resultado imediato da transmissão."""

    transmissao_id: UUID
    apuracao_id: UUID
    competencia: date
    tentativa: int
    eh_retificadora: bool
    status: TransmissaoStatus
    protocolo: str | None
    mensagem: str
    erro: str | None = None


class TransmissaoOut(BaseModel):
    """Item da listagem histórica de transmissões."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    apuracao_id: UUID
    competencia: date
    status: TransmissaoStatus
    tentativa: int
    eh_retificadora: bool
    protocolo: str | None
    criado_em: datetime
