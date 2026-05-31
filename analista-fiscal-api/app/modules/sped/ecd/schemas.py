"""Schemas Pydantic — endpoints SPED ECD (Sprint 16 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoSpedOut(StrEnum):
    ECD = "ecd"
    ECF = "ecf"
    EFD_CONTRIBUICOES = "efd_contribuicoes"
    EFD_ICMS_IPI = "efd_icms_ipi"


class StatusSpedOut(StrEnum):
    GERADO = "gerado"
    VALIDADO = "validado"
    TRANSMITIDO = "transmitido"
    ACEITO = "aceito"
    REJEITADO = "rejeitado"


class GerarEcdIn(BaseModel):
    """Input do POST /sped/ecd.

    Geração da ECD para um ano-calendário inteiro. A periodicidade
    da ECD é anual (1º jan a 31 dez do ano informado). Para situações
    especiais (cisão, fusão, encerramento intra-ano) o cliente entra
    em contato com o suporte — fora do MVP.
    """

    model_config = ConfigDict(extra="forbid")

    ano: int = Field(ge=2014, le=2099, description="Ano-calendário da ECD.")
    forcar: bool = Field(
        default=False,
        description=(
            "Sem ``forcar``, chamada idempotente devolve o arquivo ativo "
            "se já existir. Com ``forcar=True``, gera nova versão e marca "
            "a anterior como ``superseded_by``."
        ),
    )


class ArquivoSpedOut(BaseModel):
    """Resposta padrão (sem o conteúdo do .txt — use o endpoint download)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: TipoSpedOut
    periodo_inicio: date
    periodo_fim: date
    tamanho_bytes: int
    hash_arquivo: str
    status: StatusSpedOut
    algoritmo_versao: str
    supersedes: UUID | None
    superseded_by: UUID | None
    gerado_em: datetime
    transmitido_em: datetime | None
    recibo_transmissao: str | None
