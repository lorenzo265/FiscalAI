"""Schemas Pydantic v2 — Reforma Tributária (Sprint 14 PR3).

**Princípio §8.12** — todo schema de saída carrega ``observacao_estimativa``
não-vazia citando LC 214/2025 + PLP 68/2024.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Enums espelhando o domínio ───────────────────────────────────────────────


class FaseReformaOut(StrEnum):
    """Fase atual da Reforma (espelho de ``periodo_transicao.FaseReforma``)."""

    TESTE_2026 = "teste_2026"
    TRANSICAO = "transicao_2027_2032"
    PLENO = "regime_pleno_2033"


class CenarioOut(StrEnum):
    """Cenário do simulador (espelho de ``simulador.Cenario``)."""

    PESSIMISTA = "pessimista"
    REALISTA = "realista"
    OTIMISTA = "otimista"


# ── Inputs ───────────────────────────────────────────────────────────────────


class RecalcularHistoricoIn(BaseModel):
    """Payload do POST /recalcular-historico — backfill CBS/IBS informacional."""

    model_config = ConfigDict(extra="forbid")

    ano: Annotated[int, Field(ge=2026, le=2099)]
    forcar: bool = False


# ── Outputs ──────────────────────────────────────────────────────────────────


class AliquotaCBSIBSOut(BaseModel):
    """Vigência de ``aliquota_cbs_ibs`` resolvida para uma competência."""

    model_config = ConfigDict(from_attributes=True)

    fase: FaseReformaOut
    aliquota_cbs: Decimal
    aliquota_ibs: Decimal
    valid_from: date
    valid_to: date | None
    fonte_norma: str
    observacao_estimativa: str
    algoritmo_versao: str


class FaseAtualOut(BaseModel):
    """Resposta do GET /fase-atual — onde estamos no cronograma da Reforma."""

    model_config = ConfigDict(extra="forbid")

    fase: FaseReformaOut
    competencia: date
    observacao_estimativa: str
    fonte_norma: str


class CenarioSimuladoOut(BaseModel):
    """Um dos 3 cenários (pessimista/realista/otimista) do simulador."""

    model_config = ConfigDict(extra="forbid")

    cenario: CenarioOut
    aliquota_total: Decimal
    cbs_projetada: Decimal
    ibs_projetada: Decimal
    total_projetado: Decimal
    delta_absoluto: Decimal
    delta_percentual: Decimal


class CargaAtualOut(BaseModel):
    """Soma 12m dos tributos que serão substituídos por CBS+IBS."""

    model_config = ConfigDict(extra="forbid")

    pis: Decimal
    cofins: Decimal
    icms: Decimal
    iss: Decimal
    total: Decimal


class ImpactoFluxoCaixaOut(BaseModel):
    """Estimativa de capital de giro perdido com split payment 2027."""

    model_config = ConfigDict(extra="forbid")

    media_icms_mensal: Decimal
    prazo_medio_recolhimento_dias: int
    capital_giro_perdido: Decimal


class SimulacaoOut(BaseModel):
    """Resposta principal do GET /simulacao — 3 cenários + fluxo de caixa."""

    model_config = ConfigDict(extra="forbid")

    empresa_id: UUID
    periodo_inicio: date
    periodo_fim: date
    fase_atual: FaseReformaOut
    receita_anualizada: Decimal
    carga_atual: CargaAtualOut
    cenarios: list[CenarioSimuladoOut]
    impacto_fluxo_caixa_2027: ImpactoFluxoCaixaOut
    observacao_estimativa: str
    fontes_norma: list[str]
    algoritmo_versao: str


class RecalculoHistoricoOut(BaseModel):
    """Resposta do POST /recalcular-historico — contagem do backfill."""

    model_config = ConfigDict(extra="forbid")

    ano: int
    atualizados: int
    ignorados: int
    observacao_estimativa: str
