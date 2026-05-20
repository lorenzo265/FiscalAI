from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApuracaoDASIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    competencia: str = Field(
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Mês de competência no formato YYYY-MM",
    )
    receita_mes: Decimal = Field(gt=0, description="Receita bruta do mês (R$)")
    rbt12_override: Decimal | None = Field(
        default=None,
        ge=0,
        description="RBT12 explícito; se None, usa empresa.faturamento_12m",
    )
    folha_12m: Decimal | None = Field(
        default=None,
        ge=0,
        description="Folha dos últimos 12 meses — obrigatório para Anexo III/V",
    )
    sublimite_estadual: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Sublimite estadual de ICMS/ISS (LC 123 art. 19). Se None, usa o "
            "padrão R$3.600.000. Alguns estados optaram pelo sublimite reduzido "
            "R$1.800.000 — informar explicitamente nesses casos."
        ),
    )


class FaixaUsadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    faixa: int
    rbt12_ate: Decimal
    aliquota_nominal: Decimal
    parcela_deduzir: Decimal


class ApuracaoDASOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    tipo: str
    regime: str
    anexo: str
    anexo_efetivo: str
    faixa: int
    rbt12_usado: Decimal
    aliquota_nominal: Decimal
    aliquota_efetiva: Decimal
    receita_mes: Decimal
    valor_das: Decimal
    fator_r: Decimal | None
    algoritmo_versao: str
    status: str
    uf: str | None = None
    sublimite_aplicado: Decimal | None = None
    sublimite_excedido: bool = False


class ApuracaoListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    competencia: date
    tipo: str
    valor_das: Decimal
    status: str
    algoritmo_versao: str
