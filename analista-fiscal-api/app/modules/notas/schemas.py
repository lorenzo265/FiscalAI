from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.empresa.cnpj import validar_cnpj, validar_cpf


class EmitirNfseIn(BaseModel):
    """Payload para emissão de NFS-e via Focus NFe (POST /v2/nfse)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Dados do serviço
    natureza_operacao: Literal[1, 2] = Field(
        description=(
            "Natureza da operação: 1=tributação no município, "
            "2=tributação fora do município. Isenção/imunidade/exigibilidade "
            "suspensa (3-6) requer módulo de compliance (Sprint 6+)."
        ),
    )
    servico_descricao: str = Field(min_length=5, max_length=2000)
    servico_codigo: str = Field(
        min_length=1,
        max_length=20,
        description="Código de serviço municipal (LC 116/2003).",
    )
    servico_valor: Decimal = Field(gt=0, decimal_places=2)
    aliquota_iss: Decimal = Field(
        ge=Decimal("2"),
        le=Decimal("5"),
        decimal_places=4,
        description="Alíquota ISS em percentual (ex: 2.0 = 2%). Mínimo 2% (LC 116/2003 art. 8-A); máximo 5% (art. 8º, II).",
    )
    deducoes: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        decimal_places=2,
        description="Deduções da base de cálculo.",
    )

    # Dados do tomador (opcional para PF; obrigatório para PJ)
    cnpj_tomador: str | None = Field(
        default=None,
        min_length=14,
        max_length=14,
        pattern=r"^\d{14}$",
    )
    cpf_tomador: str | None = Field(
        default=None,
        min_length=11,
        max_length=11,
        pattern=r"^\d{11}$",
    )

    @field_validator("cpf_tomador")
    @classmethod
    def _validar_cpf_tomador(cls, v: str | None) -> str | None:
        if v is not None and not validar_cpf(v):
            raise ValueError(f"CPF do tomador inválido: {v}")
        return v
    razao_social_tomador: str | None = Field(default=None, max_length=255)
    email_tomador: str | None = Field(default=None, max_length=255)

    @field_validator("cnpj_tomador")
    @classmethod
    def _validar_cnpj_tomador(cls, v: str | None) -> str | None:
        if v is not None and not validar_cnpj(v):
            raise ValueError(f"CNPJ do tomador inválido: {v}")
        return v


class EmitirNfseOut(BaseModel):
    """Resultado imediato da solicitação de emissão."""

    model_config = ConfigDict(from_attributes=True)

    focus_ref: str
    status: str
    documento_fiscal_id: UUID | None = None
    mensagem: str
    aviso_iss: str | None = None


class NfseStatusOut(BaseModel):
    """Status atualizado de uma NFS-e consultada na Focus NFe."""

    model_config = ConfigDict(from_attributes=True)

    focus_ref: str
    status: str
    numero: str | None = None
    numero_rps: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    mensagem_sefaz: str | None = None
