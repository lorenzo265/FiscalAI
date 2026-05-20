"""Sync de contas + transações Pluggy (Sprint 7 PR2).

Pipeline ``sincronizar_item(item_uuid)``:
  1. Carrega ``PluggyItem`` (RLS valida tenant).
  2. GET /accounts?itemId={pluggy_item_id} → UPSERT em ``conta_bancaria``.
  3. Para cada conta, GET /transactions paginando até esgotar.
  4. UPSERT em ``transacao_bancaria`` por ``pluggy_transaction_id``.
  5. Atualiza ``pluggy_item.last_sync_at`` e status.

Idempotência total (§8.9): re-execução não cria duplicatas — UPSERT em
contas (UNIQUE pluggy_account_id) e transações (UNIQUE pluggy_transaction_id).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.shared.types import JsonObject
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.open_finance.repo import PluggyItemRepo
from app.modules.open_finance.transacoes_repo import (
    ContaBancariaRepo,
    TransacoesRepo,
)
from app.shared.exceptions import (
    ItemNaoEncontrado,
    PluggyErro,
    PluggyTimeout,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_PLUGGY_PAGE_SIZE = 200
_PLUGGY_MAX_PAGES = 50  # Bombeio de segurança — 10k transações por sync.


class _ClienteSync(Protocol):
    async def list_accounts(self, item_id: str) -> JsonObject: ...

    async def list_transactions(
        self,
        *,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int = 200,
        page: int = 1,
    ) -> JsonObject: ...


class SyncResultado:
    __slots__ = ("contas_processadas", "contas_novas", "transacoes_processadas")

    def __init__(self) -> None:
        self.contas_processadas = 0
        self.contas_novas = 0
        self.transacoes_processadas = 0


class SyncService:
    async def sincronizar_item(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_uuid: uuid.UUID,
        *,
        pluggy_client: _ClienteSync | None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> SyncResultado:
        repo_item = PluggyItemRepo(session)
        item = await repo_item.por_id(item_uuid)
        if item is None:
            raise ItemNaoEncontrado(f"PluggyItem {item_uuid} não encontrado")

        resultado = SyncResultado()
        if pluggy_client is None:
            await repo_item.atualizar_status(
                item_uuid,
                status=item.status,
                erro_codigo="PluggyIndisponivel",
            )
            await session.commit()
            return resultado

        try:
            accounts_resp = await pluggy_client.list_accounts(item.pluggy_item_id)
        except (PluggyErro, PluggyTimeout) as exc:
            await repo_item.atualizar_status(
                item_uuid,
                status="LOGIN_ERROR" if isinstance(exc, PluggyErro) else item.status,
                erro_codigo=exc.codigo,
            )
            await session.commit()
            log.warning(
                "open_finance.sync.accounts_falhou",
                item_id=str(item_uuid),
                erro=exc.codigo,
            )
            return resultado

        accounts = _lista_de(accounts_resp, "results")
        repo_conta = ContaBancariaRepo(session)
        repo_tx = TransacoesRepo(session)

        for raw in accounts:
            conta_dto = _account_para_dto(raw)
            if conta_dto is None:
                continue
            conta, novo = await repo_conta.upsert(
                tenant_id=tenant_id,
                empresa_id=item.empresa_id,
                pluggy_item_id=item.id,
                **conta_dto,
            )
            resultado.contas_processadas += 1
            if novo:
                resultado.contas_novas += 1

            # Paginação de transações
            page = 1
            while page <= _PLUGGY_MAX_PAGES:
                try:
                    tx_resp = await pluggy_client.list_transactions(
                        account_id=conta_dto["pluggy_account_id"],
                        from_date=from_date.isoformat() if from_date else None,
                        to_date=to_date.isoformat() if to_date else None,
                        page_size=_PLUGGY_PAGE_SIZE,
                        page=page,
                    )
                except (PluggyErro, PluggyTimeout) as exc:
                    log.warning(
                        "open_finance.sync.transactions_falhou",
                        item_id=str(item_uuid),
                        account_id=conta_dto["pluggy_account_id"],
                        page=page,
                        erro=exc.codigo,
                    )
                    break

                rows = _lista_de(tx_resp, "results")
                if not rows:
                    break

                lote = [
                    dto for dto in (_transacao_para_dto(r) for r in rows) if dto is not None
                ]
                if lote:
                    await repo_tx.upsert_lote(
                        tenant_id=tenant_id,
                        empresa_id=item.empresa_id,
                        conta_bancaria_id=conta.id,
                        transacoes=lote,
                    )
                    resultado.transacoes_processadas += len(lote)

                if len(rows) < _PLUGGY_PAGE_SIZE:
                    break
                page += 1

        await repo_item.atualizar_status(
            item_uuid,
            status="LOGIN_SUCCEEDED",
            last_sync_at=datetime.now(_TZ_BR),
        )
        await session.commit()

        log.info(
            "open_finance.sync.ok",
            item_id=str(item_uuid),
            contas=resultado.contas_processadas,
            contas_novas=resultado.contas_novas,
            transacoes=resultado.transacoes_processadas,
        )
        return resultado


# ── helpers puros (sem I/O) ──────────────────────────────────────────────────


def _lista_de(resp: JsonObject, chave: str) -> list[JsonObject]:
    valor = resp.get(chave)
    if not isinstance(valor, list):
        return []
    return [v for v in valor if isinstance(v, dict)]


def _account_para_dto(raw: JsonObject) -> JsonObject | None:
    """Mapeia /accounts Pluggy → kwargs do ``ContaBancariaRepo.upsert``.

    Retorna None se o registro não tem ID — não vale persistir.
    """
    pluggy_account_id = raw.get("id")
    if not pluggy_account_id:
        return None

    bank_data = raw.get("bankData") or {}
    tipo_raw = str(raw.get("type") or "").upper()
    tipo = tipo_raw if tipo_raw in {"CHECKING", "SAVINGS", "CREDIT_CARD"} else "CHECKING"

    return {
        "pluggy_account_id": str(pluggy_account_id),
        "banco_nome": _str_ou_none(raw.get("name") or bank_data.get("name")),
        "agencia": _str_ou_none(
            bank_data.get("transferNumber") or bank_data.get("agencyNumber")
        ),
        "numero": _str_ou_none(bank_data.get("accountNumber") or raw.get("number")),
        "tipo": tipo,
        "subtipo": _str_ou_none(raw.get("subtype")),
        "saldo_atual": _decimal_ou_zero(raw.get("balance")),
        "saldo_disponivel": _decimal_ou_none(raw.get("availableBalance")),
        "saldo_atualizado_em": _parse_iso_dt(raw.get("updatedAt")),
    }


def _transacao_para_dto(raw: JsonObject) -> JsonObject | None:
    pluggy_tx_id = raw.get("id")
    if not pluggy_tx_id:
        return None

    valor = _decimal_ou_none(raw.get("amount"))
    if valor is None:
        return None

    tipo_raw = str(raw.get("type") or "").upper()
    if tipo_raw not in {"CREDIT", "DEBIT"}:
        # Inferir pelo sinal do valor.
        tipo_raw = "CREDIT" if valor >= Decimal("0") else "DEBIT"

    # Garante sinal coerente: DEBIT armazenado como negativo.
    valor_signed = valor.copy_abs() if tipo_raw == "CREDIT" else -valor.copy_abs()

    data_tx = _parse_iso_date(raw.get("date"))
    if data_tx is None:
        return None

    status_raw = str(raw.get("status") or "").upper()
    status = status_raw if status_raw in {"PENDING", "CONFIRMED"} else "CONFIRMED"

    merchant = raw.get("merchant") or {}
    cnpj_raw = merchant.get("cnpj") or merchant.get("documentNumber") or ""
    cnpj_digits = "".join(c for c in str(cnpj_raw) if c.isdigit())
    merchant_cnpj = cnpj_digits if len(cnpj_digits) == 14 else None

    descricao = _str_ou_none(raw.get("description"))
    return {
        "pluggy_transaction_id": str(pluggy_tx_id),
        "data_transacao": data_tx,
        "valor": valor_signed,
        "descricao": descricao[:500] if descricao else None,
        "tipo": tipo_raw,
        "status": status,
        "categoria_pluggy": _str_ou_none(raw.get("category")),
        "merchant_cnpj": merchant_cnpj,
        "merchant_nome": _str_ou_none(merchant.get("name")),
        "raw_json": raw,
    }


def _str_ou_none(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _decimal_ou_none(v: object) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _decimal_ou_zero(v: object) -> Decimal:
    return _decimal_ou_none(v) or Decimal("0")


def _parse_iso_dt(v: object) -> datetime | None:
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_iso_date(v: object) -> date | None:
    if not isinstance(v, str):
        return None
    # Pluggy envia ISO datetime ou date — aceitamos ambos.
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
