"""Schemas Pydantic — relatórios (Sprint 12 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoRelatorio(StrEnum):
    DRE = "dre"
    BALANCO = "balanco"
    DFC = "dfc"
    INDICADORES = "indicadores"
    DRE_AUX_LP = "dre_aux_lp"


class GerarDreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    periodo_inicio: date
    periodo_fim: date
    forcar_regerar: bool = False
    resultado_financeiro: Decimal = Decimal("0")


class LinhaDreOut(BaseModel):
    rotulo: str
    valor: Decimal
    detalhes: list[str] = []


class DreOut(BaseModel):
    """Estrutura serializável de um DRE."""

    receita_bruta: LinhaDreOut
    deducoes: LinhaDreOut
    receita_liquida: LinhaDreOut
    cmv: LinhaDreOut
    lucro_bruto: LinhaDreOut
    despesas_pessoal: LinhaDreOut
    outras_despesas: LinhaDreOut
    ebitda: LinhaDreOut
    depreciacao: LinhaDreOut
    ebit: LinhaDreOut
    resultado_financeiro: LinhaDreOut
    lair: LinhaDreOut
    irpj_csll: LinhaDreOut
    lucro_liquido: LinhaDreOut
    algoritmo_versao: str


class GerarBalancoIn(BaseModel):
    """Balanço Patrimonial — snapshot na ``data_referencia`` (último dia
    do período)."""

    model_config = ConfigDict(extra="forbid")

    data_referencia: date
    forcar_regerar: bool = False


class GerarDfcIn(BaseModel):
    """DFC método indireto.

    Variações do capital de giro/imobilizado/financiamento são derivadas
    automaticamente do ``saldo_conta_mes`` no service; ``distribuicao_lucros``,
    ``emprestimos_*`` e ``aporte_capital`` aceitam override manual quando
    o plano contábil ainda não diferencia essas contas (MVP — não temos
    contas de empréstimo no plano referencial).
    """

    model_config = ConfigDict(extra="forbid")

    periodo_inicio: date
    periodo_fim: date
    forcar_regerar: bool = False
    # Overrides opcionais (default 0 = derivado do balancete quando possível).
    aporte_capital: Decimal = Decimal("0")
    emprestimos_captados: Decimal = Decimal("0")
    emprestimos_pagos: Decimal = Decimal("0")
    distribuicao_lucros: Decimal = Decimal("0")


class GerarIndicadoresIn(BaseModel):
    """Indicadores — reusa Balanço (snapshot na ``data_referencia``) e DRE
    do período. Service gera/recupera ambos automaticamente."""

    model_config = ConfigDict(extra="forbid")

    periodo_inicio: date
    periodo_fim: date
    forcar_regerar: bool = False


class GerarDreAuxLpIn(BaseModel):
    """DRE auxiliar trimestral LP — cruza apurações fiscais com DRE contábil."""

    model_config = ConfigDict(extra="forbid")

    ano: int = Field(ge=2000, le=2100)
    trimestre: int = Field(ge=1, le=4)
    forcar_regerar: bool = False


class RelatorioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: TipoRelatorio
    periodo_inicio: date
    periodo_fim: date
    payload: dict[str, object]
    algoritmo_versao: str
    superseded_by: UUID | None
    criado_em: datetime
