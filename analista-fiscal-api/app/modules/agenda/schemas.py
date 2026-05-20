from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class AgendaItemOut(BaseModel):
    id: UUID
    titulo: str
    descricao: str | None
    data_vencimento: date
    regime: str
    tipo_obrigacao: str
    status: str


class AgendaGerarIn(BaseModel):
    ano: int = Field(ge=2024, le=2035, description="Ano de competência do calendário")
    tem_funcionarios: bool = Field(
        default=False,
        description="Inclui FGTS (dia 7), eSocial S-1200 (dia 15) e GPS/INSS (dia 20, LP).",
    )
    parcelar_irpj: bool = Field(
        default=False,
        description=(
            "LP: gera 3 vencimentos por trimestre para o IRPJ/CSLL "
            "(art. 5º Lei 9.430/1996). False = apenas 1ª cota / pagamento único."
        ),
    )


class AgendaListaOut(BaseModel):
    empresa_id: UUID
    ano: int
    total: int
    itens: list[AgendaItemOut]
