"""Processamento do webhook Pluggy (Sprint 7 PR2).

Design intencionalmente simples:
  1. Validação HMAC no router (precisa do body bruto).
  2. Aqui: INSERT ON CONFLICT DO NOTHING em ``pluggy_webhook_event``
     (dedup por ``pluggy_event_id``, §8.9).
  3. Retorna sem fazer cross-tenant lookup nem disparar sync inline.

Por que não disparar sync no webhook?
  * Webhooks Pluggy são públicos e chegam sem contexto de tenant. RLS bloqueia
    a leitura de ``PluggyItem`` sem ``SET LOCAL app.tenant_id``. Fazer o
    routing aqui exigiria role privilegiada (SECURITY DEFINER), infra que o
    MVP ainda não tem.
  * Em vez disso, o worker ``sync_pluggy`` (skeleton) lê eventos não
    processados periodicamente, faz o routing com role admin e dispara
    o SyncService dentro do tenant correto.
  * Alternativamente, o cliente pode chamar
    ``POST /v1/empresas/{id}/open-finance/items/{item_uuid}/sync`` para
    forçar sync com contexto.
"""

from __future__ import annotations

from app.shared.types import JsonObject

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import PluggyWebhookEvent

log = structlog.get_logger(__name__)


class WebhookResultado:
    __slots__ = ("duplicado", "persistido")

    def __init__(self) -> None:
        self.duplicado = False
        self.persistido = False


class WebhookService:
    async def persistir(
        self,
        anon_session: AsyncSession,
        *,
        event_id: str,
        item_pluggy_id: str,
        event_type: str,
        payload: JsonObject,
    ) -> WebhookResultado:
        """Insere o evento com idempotência por ``pluggy_event_id``."""
        resultado = WebhookResultado()

        stmt = (
            pg_insert(PluggyWebhookEvent)
            .values(
                pluggy_event_id=event_id,
                pluggy_item_id=item_pluggy_id,
                event_type=event_type,
                payload_json=payload,
            )
            .on_conflict_do_nothing(constraint="uq_pluggy_webhook_event_id")
            .returning(PluggyWebhookEvent.id)
        )
        inserido = (await anon_session.execute(stmt)).scalar_one_or_none()
        await anon_session.commit()

        if inserido is None:
            resultado.duplicado = True
            log.info(
                "open_finance.webhook.duplicado",
                event_id=event_id,
                event_type=event_type,
            )
        else:
            resultado.persistido = True
            log.info(
                "open_finance.webhook.persistido",
                event_id=event_id,
                event_type=event_type,
                pluggy_item_id=item_pluggy_id,
            )
        return resultado
