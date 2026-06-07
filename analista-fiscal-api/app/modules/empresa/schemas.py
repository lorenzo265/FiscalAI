from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.empresa.cnpj import validar_cnpj


class RegimeTributario(StrEnum):
    MEI = "mei"
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"


class AnexoSimples(StrEnum):
    I = "I"  # noqa: E741 — nome do anexo fiscal brasileiro (Anexo I)
    II = "II"
    III = "III"
    IV = "IV"
    V = "V"


class PerfilUI(StrEnum):
    MEI = "mei"
    SN_SEM_FUNCIONARIOS = "sn_sem_funcionarios"
    SN_COM_FUNCIONARIOS = "sn_com_funcionarios"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"


def _derivar_perfil_ui(regime: RegimeTributario) -> PerfilUI:
    mapping: dict[RegimeTributario, PerfilUI] = {
        RegimeTributario.MEI: PerfilUI.MEI,
        RegimeTributario.SIMPLES_NACIONAL: PerfilUI.SN_SEM_FUNCIONARIOS,
        RegimeTributario.LUCRO_PRESUMIDO: PerfilUI.LUCRO_PRESUMIDO,
        RegimeTributario.LUCRO_REAL: PerfilUI.LUCRO_REAL,
    }
    return mapping[regime]


class EmpresaIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cnpj: str = Field(min_length=14, max_length=14, pattern=r"^\d{14}$")
    razao_social: str = Field(min_length=3, max_length=255)
    nome_fantasia: str | None = Field(default=None, max_length=255)
    regime_tributario: RegimeTributario
    anexo_simples: AnexoSimples | None = None
    cnae_principal: str | None = Field(default=None, max_length=10)
    municipio: str | None = Field(default=None, max_length=100)
    codigo_municipio_ibge: str | None = Field(
        default=None,
        pattern=r"^\d{7}$",
        description="Código IBGE 7-dígitos do município (exigido por Focus NFe e SERPRO PGDAS-D).",
    )
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ie: str | None = Field(default=None, max_length=20)
    im: str | None = Field(default=None, max_length=20)
    faturamento_12m: Decimal | None = Field(default=None, ge=0)

    @field_validator("cnpj")
    @classmethod
    def _validar_cnpj(cls, v: str) -> str:
        if not validar_cnpj(v):
            raise ValueError(f"CNPJ inválido: {v}")
        return v

    @field_validator("uf")
    @classmethod
    def _normalizar_uf(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class EmpresaUpdateIn(BaseModel):
    """Edição dos dados cadastrais da empresa (``PUT /v1/empresas/{id}``).

    Atualização parcial: campos omitidos permanecem inalterados. O ``cnpj`` é
    identidade imutável e **não** é aceito aqui (``extra="forbid"``); ``ativa`` e
    ``aliquota_iss_validada`` têm endpoints próprios. Quando ``regime_tributario``
    muda, ``perfil_ui`` é re-derivado no service.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    razao_social: str | None = Field(default=None, min_length=3, max_length=255)
    nome_fantasia: str | None = Field(default=None, max_length=255)
    regime_tributario: RegimeTributario | None = None
    anexo_simples: AnexoSimples | None = None
    cnae_principal: str | None = Field(default=None, max_length=10)
    municipio: str | None = Field(default=None, max_length=100)
    codigo_municipio_ibge: str | None = Field(
        default=None,
        pattern=r"^\d{7}$",
        description="Código IBGE 7-dígitos do município.",
    )
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ie: str | None = Field(default=None, max_length=20)
    im: str | None = Field(default=None, max_length=20)
    faturamento_12m: Decimal | None = Field(default=None, ge=0)

    @field_validator("uf")
    @classmethod
    def _normalizar_uf(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class EmpresaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    regime_tributario: str
    perfil_ui: str
    anexo_simples: str | None
    cnae_principal: str | None
    municipio: str | None
    codigo_municipio_ibge: str | None
    uf: str | None
    faturamento_12m: Decimal | None
    ativa: bool
    aliquota_iss_validada: bool = False


class OnboardingCnpjIn(BaseModel):
    """Input para onboarding de empresa via CNPJ (Sprint 5)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cnpj: str = Field(min_length=14, max_length=14, pattern=r"^\d{14}$")
    faturamento_12m: Decimal | None = Field(
        default=None,
        ge=0,
        description="Faturamento dos últimos 12 meses. Usado para sugerir regime.",
    )

    @field_validator("cnpj")
    @classmethod
    def _validar_cnpj(cls, v: str) -> str:
        if not validar_cnpj(v):
            raise ValueError(f"CNPJ inválido: {v}")
        return v


class MunicipioIbgeIn(BaseModel):
    """Payload do PATCH manual de código IBGE — usado quando resolver automático falha."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    codigo_municipio_ibge: str = Field(
        pattern=r"^\d{7}$",
        description="Código IBGE 7-dígitos do município (ex.: '3550308' para São Paulo).",
    )


class OnboardingResultadoOut(BaseModel):
    """Resultado do onboarding: dados da Receita Federal + regime sugerido."""

    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    porte: str
    situacao_cadastral: str
    cnae_principal: str | None
    cnae_descricao: str | None
    municipio: str | None
    codigo_municipio_ibge: str | None
    uf: str | None
    regime_sugerido: RegimeTributario
    anexo_sugerido: AnexoSimples | None
    empresa_criada: EmpresaOut | None = None
    aviso: str | None = None


# ── Sprint 19 PR4: Onboarding bundle ────────────────────────────────────────


class OnboardingBundleIn(BaseModel):
    """Payload do bootstrap de onboarding self-service.

    Mantido pequeno: o cliente normalmente chama imediatamente após criar a
    empresa, e tudo que precisa derivar (perfil, regime) já está em
    ``Empresa``.
    """

    model_config = ConfigDict(extra="forbid")

    # Data de início de vigência do plano referencial. Default é hoje no
    # service — schema deixa override opcional para onboarding retroativo.
    valid_from: str | None = Field(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        description="Data ISO (YYYY-MM-DD) de início de vigência. Default: hoje.",
    )
    welcome_digest_optin: bool = Field(
        default=False,
        description="Marca empresa para receber digest WhatsApp na próxima 2ª-feira.",
    )


class OnboardingPassoOut(BaseModel):
    """Item da checklist de próximos passos retornada pelo bundle.

    O frontend usa ``chave`` para pintar ícone, ``titulo``/``descricao`` para
    texto, e ``endpoint`` como hint do call-to-action.
    """

    model_config = ConfigDict(from_attributes=True)

    chave: str
    titulo: str
    descricao: str
    endpoint: str | None
    concluido: bool


class OnboardingBundleOut(BaseModel):
    """Resultado do bootstrap: o que foi feito + checklist do que falta."""

    model_config = ConfigDict(from_attributes=True)

    empresa_id: UUID
    perfil_ui: PerfilUI
    plano_contas_criadas: int
    plano_contas_existentes: int
    welcome_digest_optin: bool
    proximos_passos: list[OnboardingPassoOut]
