"""Schemas Pydantic — endpoints SPED EFD (Sprint 17)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# Reusa o ``ArquivoSpedOut`` do módulo ECD — schema é genérico por tipo.
from app.modules.sped.ecd.schemas import ArquivoSpedOut

__all__ = [
    "ArquivoSpedOut",
    "GerarEfdContribuicoesIn",
    "GerarEfdIcmsIpiIn",
]


class GerarEfdContribuicoesIn(BaseModel):
    """Input do POST ``/sped/efd-contribuicoes``.

    Geração mensal — ``competencia`` é qualquer dia do mês desejado; o
    service deriva ``periodo_inicio`` (1º dia) e ``periodo_fim`` (último
    dia) automaticamente.
    """

    model_config = ConfigDict(extra="forbid")

    competencia: date = Field(
        description=(
            "Mês de competência da EFD-Contribuições (qualquer dia do mês "
            "serve — service normaliza para o 1º dia)."
        ),
    )
    forcar: bool = Field(
        default=False,
        description=(
            "Sem ``forcar``, chamada idempotente devolve 409 se já existir "
            "arquivo ativo. Com ``forcar=True``, gera nova versão e marca a "
            "anterior como ``superseded_by`` (§8.2)."
        ),
    )


class GerarEfdIcmsIpiIn(BaseModel):
    """Input do POST ``/sped/efd-icms-ipi``.

    Geração mensal — semântica idêntica à EFD-Contribuições.
    """

    model_config = ConfigDict(extra="forbid")

    competencia: date = Field(
        description=(
            "Mês de competência da EFD ICMS-IPI (qualquer dia do mês serve "
            "— service normaliza para o 1º dia)."
        ),
    )
    forcar: bool = Field(
        default=False,
        description=(
            "Sem ``forcar``, chamada idempotente devolve 409 se já existir "
            "arquivo ativo. Com ``forcar=True``, gera nova versão e marca a "
            "anterior como ``superseded_by`` (§8.2)."
        ),
    )
