"""Schemas Pydantic do módulo Open Finance (Sprint 7 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StatusItem(StrEnum):
    CREATING = "CREATING"
    UPDATING = "UPDATING"
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_ERROR = "LOGIN_ERROR"
    WAITING_USER_INPUT = "WAITING_USER_INPUT"
    OUTDATED = "OUTDATED"
    DELETED = "DELETED"


class ConnectTokenOut(BaseModel):
    """Resposta do POST /connect-token — frontend usa ``connect_token`` no widget."""

    connect_token: str
    expires_at: datetime | None = None
    aviso: str = Field(
        default=(
            "Token válido por ~30 minutos. O produto opera em modo READ-ONLY: "
            "não iniciamos pagamentos automaticamente."
        )
    )


class RegistrarItemIn(BaseModel):
    """Frontend posta o ``item_id`` retornado pelo widget após sucesso."""

    model_config = ConfigDict(extra="forbid")

    pluggy_item_id: str = Field(min_length=8, max_length=80)


class PluggyItemOut(BaseModel):
    """Representa um item Pluggy persistido."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    pluggy_item_id: str
    connector_id: int | None
    connector_nome: str | None
    status: StatusItem
    last_sync_at: datetime | None
    ativo: bool
    criado_em: datetime


# ── Sync / contas / transações (PR2) ─────────────────────────────────────────


class TipoConta(StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CREDIT_CARD = "CREDIT_CARD"


class TipoTransacao(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class StatusTransacao(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"


class SyncOut(BaseModel):
    """Resultado de um sync manual."""

    contas_processadas: int
    contas_novas: int
    transacoes_processadas: int


class ContaBancariaOut(BaseModel):
    """Item da listagem de contas."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pluggy_item_id: UUID
    pluggy_account_id: str
    banco_nome: str | None
    agencia: str | None
    numero: str | None
    tipo: TipoConta
    subtipo: str | None
    moeda: str
    saldo_atual: Decimal
    saldo_disponivel: Decimal | None
    saldo_atualizado_em: datetime | None


class TransacaoBancariaOut(BaseModel):
    """Item da listagem de transações."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conta_bancaria_id: UUID
    pluggy_transaction_id: str
    data_transacao: date
    valor: Decimal
    descricao: str | None
    tipo: TipoTransacao
    status: StatusTransacao
    categoria_pluggy: str | None
    merchant_cnpj: str | None
    merchant_nome: str | None


class WebhookAckOut(BaseModel):
    """Resposta ao webhook Pluggy."""

    recebido: bool
    duplicado: bool
