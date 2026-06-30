"""Schemas — cofre de certificado A1.

Entrada: arquivo .p12 em base64 + senha. Saída: SÓ metadados (CN, CNPJ,
validade, fingerprint, status) — nunca o .p12 nem a senha (§8.7).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertificadoUploadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pfx_base64: str = Field(
        ...,
        min_length=1,
        description="Conteúdo do arquivo .p12/.pfx codificado em base64.",
    )
    senha: str = Field(
        ...,
        min_length=1,
        description="Senha do certificado A1 (usada para abrir o .p12).",
    )


class CertificadoStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    cn_titular: str
    cnpj_titular: str | None
    validade_inicio: datetime
    validade_fim: datetime
    fingerprint: str
    ativo: bool
    criado_em: datetime


class RemocaoCertificadoOut(BaseModel):
    """Confirmação da desativação do certificado."""

    removido: bool
