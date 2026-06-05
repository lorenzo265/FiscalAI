"""Schemas Pydantic — provisões trabalhistas (Sprint 8 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoProvisao(StrEnum):
    FERIAS = "ferias"
    DECIMO_TERCEIRO = "13_salario"
    INSS_FERIAS = "inss_ferias"
    INSS_13 = "inss_13"
    FGTS_FERIAS = "fgts_ferias"
    FGTS_13 = "fgts_13"


class GerarProvisaoIn(BaseModel):
    """Folha agregada da empresa no mês. Funcionário individual entra na Sprint 10."""

    model_config = ConfigDict(extra="forbid")

    folha_mes_total: Decimal = Field(
        ge=0,
        decimal_places=2,
        description="Total bruto da folha do mês (BRL).",
    )
    rat_sat: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=Decimal("0.10"),
        description=(
            "Alíquota RAT/SAT (Lei 8.212/91 art.22 II), já multiplicada pelo FAP. "
            "Aplica-se a SN Anexo IV, Lucro Presumido e Lucro Real. "
            "Default 0%% — piso conservador até seed definitivo por CNAE/grau de risco "
            "(ver docs/pendencias/rat-fap-terceiros-seed.md). "
            "Exemplo: RAT 2%% × FAP 1,0 = 0,02."
        ),
    )
    aliquota_terceiros: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=Decimal("0.10"),
        description=(
            "Alíquota Terceiros/Sistema S (SENAI, SESI, SESC, SEBRAE, etc.). "
            "Aplica-se a SN Anexo IV, Lucro Presumido e Lucro Real. "
            "Default 0%% — piso conservador até seed definitivo por CNAE. "
            "Valor típico: ~5,8%% para indústria/comércio. "
            "(ver docs/pendencias/rat-fap-terceiros-seed.md)."
        ),
    )


class ProvisaoMensalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    tipo: TipoProvisao
    base_calculo: Decimal
    aliquota: Decimal
    valor_provisao: Decimal
    funcionario_id: UUID | None


class GerarProvisaoOut(BaseModel):
    """Resultado do lote mensal."""

    competencia: date
    linhas_geradas: int  # 0 a 6 (pula se idempotente; 6 num run novo)
    linhas_existentes: int  # já estavam persistidas
    valor_total_provisionado: Decimal
    inss_aplicavel: bool
    algoritmo_versao: str
