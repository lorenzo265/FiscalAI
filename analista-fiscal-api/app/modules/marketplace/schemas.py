"""Schemas Pydantic — marketplace (Sprint 13 PR1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CrcStatus(StrEnum):
    ATIVO = "ativo"
    SUSPENSO = "suspenso"
    BAIXADO = "baixado"


class CadastrarParceiroIn(BaseModel):
    """Payload de auto-cadastro de contador parceiro (público).

    Cadastro nasce ``ativo=False`` — só aparece em matching após curadoria
    aprovar (POST /v1/admin/marketplace/parceiros/{id}/aprovar).
    """

    model_config = ConfigDict(extra="forbid")

    nome: Annotated[str, Field(min_length=3, max_length=255)]
    email: EmailStr
    telefone: Annotated[str, Field(min_length=10, max_length=20)]
    cpf: Annotated[str | None, Field(default=None, pattern=r"^\d{11}$")]
    cnpj: Annotated[str | None, Field(default=None, pattern=r"^\d{14}$")]
    crc_numero: Annotated[str, Field(pattern=r"^\d{1,9}$")]
    crc_uf: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    especialidades: Annotated[list[str], Field(min_length=1)]
    uf_atuacao: list[str] | None = None
    oab_numero: Annotated[str | None, Field(default=None, max_length=20)]
    oab_uf: Annotated[str | None, Field(default=None, pattern=r"^[A-Z]{2}$")]
    sla_resposta_horas: Annotated[int, Field(default=24, ge=1, le=720)]


class ParceiroOut(BaseModel):
    """Visão pública (cliente PME) — campos sensíveis omitidos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    crc_numero: str
    crc_uf: str
    crc_status: CrcStatus
    especialidades: list[str]
    uf_atuacao: list[str] | None
    rating_medio: Decimal | None
    total_consultas: int
    taxa_resposta_horas: int | None
    sla_resposta_horas: int
    oab_numero: str | None
    oab_uf: str | None
    ativo: bool


class ParceiroAdminOut(ParceiroOut):
    """Visão administrativa — inclui contato + timestamps."""

    email: EmailStr
    telefone: str
    cpf: str | None
    cnpj: str | None
    crc_status_atualizado_em: datetime | None
    aceitou_nda_lgpd_em: datetime | None
    created_at: datetime


class AprovarParceiroIn(BaseModel):
    """Aprovação da curadoria — opcionalmente registra NDA + LGPD."""

    model_config = ConfigDict(extra="forbid")

    registrar_aceite_nda_lgpd: bool = True


# ── Consulta marketplace (PR2) ──────────────────────────────────────────────


class CategoriaIn(StrEnum):
    CONSULTA_RAPIDA = "consulta_rapida"
    ANALISE_INTIMACAO_SIMPLES = "analise_intimacao_simples"
    ANALISE_INTIMACAO_COMPLEXA = "analise_intimacao_complexa"
    PARECER_TECNICO = "parecer_tecnico"
    PETICAO_ADMINISTRATIVA = "peticao_administrativa"
    DEFESA_AUTO = "defesa_auto"
    PLANEJAMENTO_TRIBUTARIO = "planejamento_tributario"
    HOLDING = "holding"
    SUCESSAO = "sucessao"


class StatusConsultaIn(StrEnum):
    ABERTA = "aberta"
    ATRIBUIDA = "atribuida"
    ACEITA = "aceita"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"


class CriarConsultaIn(BaseModel):
    """Cliente PME abre consulta — escolhe categoria + (opcional) parceiro."""

    model_config = ConfigDict(extra="forbid")

    categoria: CategoriaIn
    pergunta: Annotated[str, Field(min_length=10, max_length=4000)]
    consentimento_compartilhamento: bool
    contador_id: UUID | None = None
    valor_consulta: Annotated[Decimal | None, Field(default=None, gt=0)]


class ResponderConsultaIn(BaseModel):
    """Parceiro envia resposta + anexos opcionais."""

    model_config = ConfigDict(extra="forbid")

    contador_id: UUID
    resposta_resumo: Annotated[str, Field(min_length=10, max_length=10000)]
    arquivos_anexos: list[dict[str, str]] | None = None


class AceitarConsultaIn(BaseModel):
    """Parceiro aceita consulta atribuída."""

    model_config = ConfigDict(extra="forbid")

    contador_id: UUID


class AvaliarConsultaIn(BaseModel):
    """Cliente avalia consulta concluída (1–5)."""

    model_config = ConfigDict(extra="forbid")

    rating: Annotated[int, Field(ge=1, le=5)]
    comentario: Annotated[str | None, Field(default=None, max_length=2000)]


class ConsultaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    usuario_id: UUID
    contador_id: UUID | None
    categoria: CategoriaIn
    pergunta: str | None
    status: StatusConsultaIn
    valor_consulta: Decimal
    comissao_plataforma: Decimal
    resposta_resumo: str | None
    rating_cliente: int | None
    sla_aceitar_ate: datetime
    sla_responder_ate: datetime
    aberta_em: datetime
    aceita_em: datetime | None
    respondida_em: datetime | None
    paga_em: datetime | None
    snapshot_versao: str


class ParceiroSugeridoOut(BaseModel):
    """Payload enxuto exibido pelo assistente quando detecta out-of-scope."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    crc_numero: str
    crc_uf: str
    especialidades: list[str]
    uf_atuacao: list[str] | None
    rating_medio: Decimal | None
    total_consultas: int
    taxa_resposta_horas: int | None
    sla_aceitar_horas: int
    oab_numero: str | None


# ── Auth + dashboard parceiro (PR3) ─────────────────────────────────────────


class DefinirSenhaParceiroIn(BaseModel):
    """Define senha inicial do parceiro (admin)."""

    model_config = ConfigDict(extra="forbid")

    senha: Annotated[str, Field(min_length=8, max_length=72)]


class LoginParceiroIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    senha: Annotated[str, Field(min_length=8, max_length=72)]


class TokenParceiroOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DashboardParceiroOut(BaseModel):
    """Agregados consumidos pelo painel do parceiro."""

    contador_id: UUID
    nome: str
    rating_medio: Decimal | None
    total_consultas: int
    taxa_resposta_horas: int | None
    consultas_abertas: int
    consultas_concluidas_mes: int
    valor_liquido_mes: Decimal


# ── Pagamento (PR3) ─────────────────────────────────────────────────────────


class StatusCobrancaIn(StrEnum):
    PENDENTE = "pendente"
    PAGA = "paga"
    FALHOU = "falhou"
    CANCELADA = "cancelada"


class CobrancaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consulta_id: UUID
    provider: str
    provider_externo_id: str | None
    valor: Decimal
    status: StatusCobrancaIn
    checkout_url: str | None
    criado_em: datetime
    paga_em: datetime | None
    cancelada_em: datetime | None


class WebhookPagamentoIn(BaseModel):
    """Payload do webhook do provider de pagamento.

    Em prod o provider envia mais campos (assinatura, timestamp, fees) — aqui
    só os essenciais. Endpoint valida HMAC via ``X-Provider-Signature``.
    """

    model_config = ConfigDict(extra="forbid")

    provider_externo_id: Annotated[str, Field(min_length=1, max_length=120)]
    status: StatusCobrancaIn
