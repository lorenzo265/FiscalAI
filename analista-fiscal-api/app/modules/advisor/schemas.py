"""Schemas Pydantic v2 — AI Advisor (Sprint 15 PR1).

Input/output do bounded context. Espelha as enums do algoritmo puro
``calcula_anomalias`` para garantir contrato type-safe end-to-end.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Enums espelhando o domínio ───────────────────────────────────────────────


class TipoTributoOut(StrEnum):
    DAS = "das"
    IRPJ = "irpj"
    CSLL = "csll"
    PIS = "pis"
    COFINS = "cofins"
    ISS = "iss"
    ICMS = "icms"


class SeveridadeOut(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class MetodoOut(StrEnum):
    ZSCORE = "zscore"
    IQR = "iqr"


# ── Inputs ───────────────────────────────────────────────────────────────────


class DispensarAnomaliaIn(BaseModel):
    """Payload do POST /advisor/anomalias/{id}/dispensar."""

    model_config = ConfigDict(extra="forbid")

    motivo: Annotated[str, Field(min_length=3, max_length=500)]


# ── Outputs ──────────────────────────────────────────────────────────────────


class AnomaliaOut(BaseModel):
    """Snapshot persistido de ``anomalia_fiscal``."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    empresa_id: UUID
    tipo: TipoTributoOut
    competencia: date
    severidade: SeveridadeOut
    valor_observado: Decimal
    valor_esperado: Decimal
    z_score: Decimal
    delta_percentual: Decimal
    metodo: MetodoOut
    amostra_n: int
    mensagem: str
    algoritmo_versao: str
    detectado_em: datetime
    dispensada_em: datetime | None
    dispensada_por: UUID | None
    motivo_dispensa: str | None


# ── Sprint 15 PR2 — Sugestões de otimização ─────────────────────────────────


class SeveridadeSugestaoOut(StrEnum):
    """Urgência da sugestão (não confundir com severidade da anomalia)."""

    INFORMATIVA = "informativa"
    MEDIA = "media"
    ALTA = "alta"


class SugestaoOut(BaseModel):
    """Item da lista devolvida por GET /advisor/sugestoes."""

    model_config = ConfigDict(extra="forbid")

    codigo: str
    titulo: str
    descricao: str
    severidade: SeveridadeSugestaoOut
    economia_anual_estimada: Decimal | None
    fonte_norma: str
    detalhes: dict[str, str]
    observacao_estimativa: str
    algoritmo_versao: str


class ListaSugestoesOut(BaseModel):
    """Envelope com metadados — facilita evolução (paginação, cache headers)."""

    model_config = ConfigDict(extra="forbid")

    competencia_referencia: date
    total: int
    sugestoes: list[SugestaoOut]


# ── Sprint 15 PR3 — Weekly digest ────────────────────────────────────────────


class FonteRedacaoOut(StrEnum):
    TEMPLATE = "template"
    LLM_GEMINI = "llm_gemini_flash"
    LLM_FALLBACK = "llm_fallback"


class StatusDigestOut(StrEnum):
    PREPARADO = "preparado"
    ENVIADO = "enviado"
    CANCELADO = "cancelado"
    FALHOU = "falhou"  # Sprint 15.5 — 5 tentativas de envio sem sucesso


class GerarDigestIn(BaseModel):
    """Payload do POST /advisor/digest — controla idempotência + canal."""

    model_config = ConfigDict(extra="forbid")

    forcar: bool = False  # True → regera e supersede a versão da semana
    usar_llm: bool = False  # opt-in para Gemini Flash redigir o texto


class DigestOut(BaseModel):
    """Snapshot persistido de ``digest_semanal``."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    empresa_id: UUID
    semana_iso: str
    periodo_inicio: date
    periodo_fim: date
    texto_redigido: str
    fonte_redacao: FonteRedacaoOut
    citacoes: list[str]
    status: StatusDigestOut
    llm_provider: str | None
    custo_usd: Decimal | None
    tokens_input: int | None
    tokens_output: int | None
    enviado_via_whatsapp_em: datetime | None
    # Sprint 15.5 — auditoria do envio
    tentativas_envio: int
    ultimo_erro_envio: str | None
    enviado_template_name: str | None
    algoritmo_versao: str
    criado_em: datetime


class ListaDigestsOut(BaseModel):
    """Envelope da listagem GET /advisor/digests."""

    model_config = ConfigDict(extra="forbid")

    total: int
    digests: list[DigestOut]
