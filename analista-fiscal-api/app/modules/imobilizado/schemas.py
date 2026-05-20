"""Schemas Pydantic — imobilizado (Sprint 8 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoriaBem(StrEnum):
    IMOVEL = "imovel"
    EDIFICACAO = "edificacao"
    VEICULO = "veiculo"
    MAQUINA = "maquina"
    COMPUTADOR = "computador"
    MOVEL = "movel"
    OUTRO = "outro"


class MetodoDepreciacao(StrEnum):
    LINEAR = "linear"
    SOMA_DIGITOS = "soma_digitos"
    UNIDADES_PRODUZIDAS = "unidades_produzidas"


class CadastrarBemIn(BaseModel):
    """Cadastro de bem. Taxa e vida útil são opcionais — se omitidos,
    resolvidos via ``TabelaDepreciacaoRfb`` pela categoria."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    descricao: str = Field(min_length=2, max_length=255)
    categoria: CategoriaBem
    data_aquisicao: date
    valor_aquisicao: Decimal = Field(gt=0, decimal_places=2)
    documento_fiscal_id: UUID | None = None
    conta_contabil_id: UUID | None = None
    taxa_depreciacao_anual: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=4)
    vida_util_meses: int | None = Field(default=None, ge=1, le=1200)
    valor_residual: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    metodo_depreciacao: MetodoDepreciacao = MetodoDepreciacao.LINEAR


class BaixarBemIn(BaseModel):
    """Baixa do bem (alienação, sinistro, perda)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    data_baixa: date
    motivo_baixa: str = Field(min_length=2, max_length=255)


class BemImobilizadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    descricao: str
    categoria: CategoriaBem
    data_aquisicao: date
    valor_aquisicao: Decimal
    taxa_depreciacao_anual: Decimal
    vida_util_meses: int
    valor_residual: Decimal
    metodo_depreciacao: MetodoDepreciacao
    documento_fiscal_id: UUID | None
    data_baixa: date | None
    motivo_baixa: str | None
    ativo: bool
    criado_em: datetime


class DepreciacaoMensalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bem_id: UUID
    competencia: date
    valor_depreciado: Decimal
    valor_acumulado: Decimal
    saldo_contabil: Decimal


class GerarDepreciacaoOut(BaseModel):
    """Resultado do lote mensal."""

    competencia: date
    bens_processados: int
    bens_depreciados: int  # quantos receberam parcela > 0
    bens_totalmente_depreciados: int
    valor_total_depreciado: Decimal
    algoritmo_versao: str
