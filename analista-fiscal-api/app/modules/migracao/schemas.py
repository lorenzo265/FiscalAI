"""Schemas Pydantic — migração SPED (Sprint 18 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import JsonObject


class FonteLote(StrEnum):
    SPED_ECD = "sped_ecd"
    SPED_ECF = "sped_ecf"
    SPED_EFD_CONTRIBUICOES = "sped_efd_contribuicoes"
    SPED_EFD_ICMS_IPI = "sped_efd_icms_ipi"
    CSV_BALANCETE = "csv_balancete"
    CSV_RAZAO = "csv_razao"


class StatusLote(StrEnum):
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"


class LoteImportacaoOut(BaseModel):
    """Resposta do upload/polling de lote de importação SPED."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    empresa_id: UUID
    fonte: FonteLote
    arquivo_sped_id: UUID | None
    nome_arquivo: str | None
    hash_arquivo: str | None
    status: StatusLote
    iniciado_em: datetime
    concluido_em: datetime | None
    resumo: JsonObject | None = Field(
        default=None,
        description="Contagens estruturadas (lançamentos criados, ignorados, etc.)",
    )
    erros: JsonObject | None = Field(
        default=None,
        description="Lista de warnings/erros estruturados (conta ausente, etc.)",
    )
    algoritmo_versao: str


class ResumoImportacaoEcd(BaseModel):
    """Sub-resumo específico de ECD para o front exibir."""

    model_config = ConfigDict(extra="forbid")

    cnpj_arquivo: str
    inicio_exercicio: date
    fim_exercicio: date
    contas_no_plano: int
    lancamentos_no_arquivo: int
    lancamentos_criados: int
    lancamentos_existentes: int  # idempotência
    lancamentos_pulados: int  # warnings
    saldos_periodicos: int
