"""Schemas Pydantic — endpoints SPED ECF (Sprint 16 PR2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Reusa ArquivoSpedOut da PR1 (mesma estrutura serve para ECD e ECF).
from app.modules.sped.ecd.schemas import ArquivoSpedOut as ArquivoSpedOut

__all__ = ["GerarEcfIn", "ArquivoSpedOut"]


class GerarEcfIn(BaseModel):
    """Input do POST /sped/ecf.

    Anual; cobre todos os 4 trimestres do ano-calendário. Requer que as
    4 apurações IRPJ + 4 CSLL trimestrais já existam em ``apuracao_fiscal``
    (Sprint 11 PR1).
    """

    model_config = ConfigDict(extra="forbid")

    ano: int = Field(ge=2014, le=2099, description="Ano-calendário da ECF.")
    forcar: bool = Field(
        default=False,
        description=(
            "Sem ``forcar``, chamada idempotente devolve 409 ``SpedJaGerado`` "
            "se já existe ativo. Com ``forcar=true``, gera nova versão e "
            "marca a anterior como ``superseded_by``."
        ),
    )
