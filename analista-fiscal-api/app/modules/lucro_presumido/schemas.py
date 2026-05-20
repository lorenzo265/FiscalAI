"""Schemas Pydantic — Lucro Presumido (Sprint 11 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApurarIrpjCsllTrimestralIn(BaseModel):
    """Input para apurar IRPJ ou CSLL de um trimestre completo."""

    model_config = ConfigDict(extra="forbid")

    ano: Annotated[int, Field(ge=2000, le=2100)]
    trimestre: Annotated[int, Field(ge=1, le=4)]
    receita_bruta_trimestre: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    ganhos_capital: Annotated[Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))]
    receitas_aplicacoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    outras_adicoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    meses_periodo: Annotated[int, Field(ge=1, le=3, default=3)]
    irrf_a_compensar: Annotated[
        Decimal,
        Field(
            ge=0,
            decimal_places=2,
            default=Decimal("0"),
            description=(
                "IRRF retido na fonte (Lei 9.430 art. 64) deduzido do IRPJ devido. "
                "Aplica-se apenas à apuração de IRPJ — ignorado para CSLL. "
                "Inclui saldo credor de IRRF acumulado de trimestres anteriores."
            ),
        ),
    ]


class ApurarPisCofinsMensalIn(BaseModel):
    """Input para apurar PIS ou Cofins de um mês."""

    model_config = ConfigDict(extra="forbid")

    competencia: date
    receita_bruta_mes: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    exclusoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]


class ApuracaoLpOut(BaseModel):
    """Resultado persistido — reusa ``apuracao_fiscal``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    tipo: str
    regime: str
    valor_total: Decimal
    algoritmo_versao: str
    output_jsonb: dict[str, object]
    criado_em: datetime
    status: str

    @classmethod
    def from_apuracao(cls, apuracao: object) -> ApuracaoLpOut:
        from app.shared.db.models import ApuracaoFiscal

        assert isinstance(apuracao, ApuracaoFiscal)
        valor_total = _extrair_valor_total(apuracao.tipo, apuracao.output_jsonb)
        return cls(
            id=apuracao.id,
            empresa_id=apuracao.empresa_id,
            competencia=apuracao.competencia,
            tipo=apuracao.tipo,
            regime=apuracao.regime,
            valor_total=valor_total,
            algoritmo_versao=apuracao.algoritmo_versao,
            output_jsonb=apuracao.output_jsonb,
            criado_em=apuracao.created_at,
            status=apuracao.status,
        )


def _extrair_valor_total(tipo: str, output: dict[str, object]) -> Decimal:
    """Mapeia o campo principal de cada tipo para `valor_total` no Out.

    Para IRPJ usa ``irpj_devido`` (valor a recolher após IRRF compensado).
    Fallback para ``irpj_total`` mantém compatibilidade com apurações antigas
    geradas pela v1 do algoritmo (sem campo irpj_devido).
    """
    if tipo == "irpj":
        valor = output.get("irpj_devido")
        if valor is None:
            valor = output.get("irpj_total", "0")
        return Decimal(str(valor))
    if tipo == "csll":
        return Decimal(str(output.get("csll", "0")))
    if tipo in ("pis", "cofins"):
        return Decimal(str(output.get("tributo", "0")))
    return Decimal("0")


class PresuncaoResolvidaOut(BaseModel):
    """Helper diagnóstico: qual grupo o sistema escolheu para o CNAE."""

    grupo_atividade: str
    percentual_irpj: Decimal
    percentual_csll: Decimal
    cnae_pattern: str | None
    prioridade: int
    fonte: str
