"""Schemas Pydantic — ICMS (Sprint 11 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApurarIcmsMensalIn(BaseModel):
    """Inputs do apurador mensal — débito/crédito vêm somados externamente
    (do balancete ICMS ou do livro de saídas/entradas). PR2 não soma NFs
    automaticamente — fica para uma sprint de integração com o módulo
    contabil/ingestao.
    """

    model_config = ConfigDict(extra="forbid")

    competencia: date
    debito: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    credito: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    saldo_credor_anterior: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    ajustes_devedores: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    ajustes_credores: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]


class ApuracaoIcmsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    tipo: str
    regime: str
    icms_a_recolher: Decimal
    saldo_credor_a_transportar: Decimal
    algoritmo_versao: str
    output_jsonb: dict[str, object]
    status: str
    criado_em: datetime

    @classmethod
    def from_apuracao(cls, apuracao: object) -> ApuracaoIcmsOut:
        from app.shared.db.models import ApuracaoFiscal

        assert isinstance(apuracao, ApuracaoFiscal)
        out = apuracao.output_jsonb
        return cls(
            id=apuracao.id,
            empresa_id=apuracao.empresa_id,
            competencia=apuracao.competencia,
            tipo=apuracao.tipo,
            regime=apuracao.regime,
            icms_a_recolher=Decimal(str(out.get("icms_a_recolher", "0"))),
            saldo_credor_a_transportar=Decimal(
                str(out.get("saldo_credor_a_transportar", "0"))
            ),
            algoritmo_versao=apuracao.algoritmo_versao,
            output_jsonb=out,
            status=apuracao.status,
            criado_em=apuracao.created_at,
        )
