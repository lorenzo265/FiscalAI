"""Schemas Pydantic do módulo de certidões (Sprint 6)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertidaoTipo(StrEnum):
    """Tipos de certidão tratados pelo MVP — §9.2 do Plano."""

    CND = "CND"  # Certidão Negativa de Débitos federal (RFB/PGFN)
    CRF = "CRF"  # Certificado de Regularidade do FGTS (Caixa)
    CNDT = "CNDT"  # Certidão Negativa de Débitos Trabalhistas (TST)


class CertidaoStatus(StrEnum):
    NEGATIVA = "negativa"
    POSITIVA = "positiva"
    POSITIVA_COM_EFEITOS_DE_NEGATIVA = "positiva_com_efeitos_de_negativa"
    EMITIDA = "emitida"
    PROCESSANDO = "processando"
    ERRO = "erro"


class CertidaoOut(BaseModel):
    """Representa uma emissão de certidão persistida."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: CertidaoTipo
    numero: str | None
    status: CertidaoStatus
    emitida_em: datetime
    valid_until: date | None
    pdf_storage_key: str | None


class EmitirCertidaoOut(BaseModel):
    """Resultado imediato da solicitação de emissão (assíncrono ou síncrono)."""

    certidao_id: UUID
    tipo: CertidaoTipo
    status: CertidaoStatus
    numero: str | None
    valid_until: date | None
    mensagem: str
    aviso: str | None = Field(
        default=None,
        description=(
            "Aviso adicional — p.ex. quando a certidão é positiva ou quando "
            "houve fallback para o canal de scraping."
        ),
    )
