"""Processamento do webhook Pluggy (Sprint 7 PR2 / S1 Plataforma).

Design:
  1. Validação HMAC no router (precisa do body bruto).
  2. Aqui: INSERT ON CONFLICT DO NOTHING em ``pluggy_webhook_event``
     (dedup por ``pluggy_event_id``, §8.9).
  3. Enfileira task Celery ``processar_webhook_events_pendentes`` com
     ``idempotency_key`` e ``pluggy_item_id`` para routing cross-tenant.

Por que não disparar sync inline no webhook?
  * Webhooks Pluggy são públicos e chegam sem contexto de tenant. RLS bloqueia
    a leitura de ``PluggyItem`` sem ``SET LOCAL app.tenant_id``. Fazer o
    routing aqui exigiria role privilegiada (SECURITY DEFINER).
  * A task ``processar_webhook_events_pendentes`` lê eventos com role admin
    (bypass RLS controlado) e faz routing pluggy_item_id → tenant_id,
    disparando ``SyncService`` dentro do tenant correto.
  * Quando Celery não está instalado (stub), o comportamento é preservado:
    o evento fica persistido e o beat schedule drena depois (fallback seguro).
  * Sync manual disponível via
    ``POST /v1/empresas/{id}/open-finance/items/{item_uuid}/sync``.

Idempotência (§8.9):
  * ``task_id = f"webhook-sync-{event_id}"`` — Celery descarta re-enqueue
    com o mesmo task_id no broker. Adicionalmente, a task verifica
    ``processado=false`` antes de processar (dedup em DB).

RLS / tenant (§8.7):
  * Webhook é cross-tenant por natureza. O ``tenant_id`` NÃO é propagado
    aqui — a task faz o routing como admin. Veja ``sync_pluggy.py``.
"""

from __future__ import annotations

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import PluggyWebhookEvent
from app.shared.types import JsonObject

# Imports da camada de workers — lazy-safe: os módulos existem em runtime
# independentemente de o Celery estar instalado (stub dual-mode).
from app.workers.celery_app import enqueue
from app.workers.tasks.sync_pluggy import processar_webhook_events_pendentes

log = structlog.get_logger(__name__)


class WebhookResultado:
    """Resultado do processamento de um evento de webhook."""

    __slots__ = ("duplicado", "persistido", "enfileirado")

    def __init__(self) -> None:
        self.duplicado = False
        self.persistido = False
        self.enfileirado = False


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
        """Insere o evento com idempotência por ``pluggy_event_id`` e enfileira sync.

        Fluxo:
        1. INSERT ON CONFLICT DO NOTHING — idempotência garantida (§8.9).
        2. Se evento novo (não duplicado), enfileira
           ``processar_webhook_events_pendentes`` com ``idempotency_key=event_id``
           e ``pluggy_item_id`` para routing cross-tenant na task.
        3. Se Celery não está instalado (stub), o enqueue é no-op + log;
           o beat schedule ``open_finance.processar_webhook_events``
           (a cada 5min) drena os eventos pendentes como fallback.
        """
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
            resultado.enfileirado = _enfileirar_sync(
                event_id=event_id,
                item_pluggy_id=item_pluggy_id,
            )
        return resultado


def _enfileirar_sync(*, event_id: str, item_pluggy_id: str) -> bool:
    """Enfileira a task de processamento de webhook events.

    Retorna True se enfileirado no broker (Celery real), False se stub.

    Idempotência (§8.9): ``task_id = f"webhook-sync-{event_id}"`` garante
    que re-enqueue do mesmo evento é descartado pelo broker. A task em si
    também verifica ``processado=false`` antes de agir (dedup em DB).

    Separado de ``WebhookService.persistir`` para facilitar teste unitário:
    o teste mocka ``_enfileirar_sync`` sem precisar de broker nem sessão.

    RLS (§8.7): tenant_id NÃO é propagado aqui. A task faz routing admin:
    pluggy_item_id → PluggyItem.tenant_id.
    """
    # Celery real: ``apply_async`` existe na task → usa task_id como idempotency_key
    # e passa pluggy_item_id para que a task priorize este item específico.
    apply_async = getattr(processar_webhook_events_pendentes, "apply_async", None)
    if apply_async is not None:
        try:
            apply_async(
                kwargs={"pluggy_item_id": item_pluggy_id},
                task_id=f"webhook-sync-{event_id}",
            )
            log.info(
                "open_finance.webhook.enfileirado",
                event_id=event_id,
                pluggy_item_id=item_pluggy_id,
                task_id=f"webhook-sync-{event_id}",
            )
            return True
        except Exception:
            log.exception(
                "open_finance.webhook.enqueue_falhou",
                event_id=event_id,
                pluggy_item_id=item_pluggy_id,
            )
            # Fallback: evento está no DB, beat schedule drena depois.
            return False
    else:
        # Stub (sem Celery instalado) — usa helper enqueue para log estruturado.
        # O beat schedule "open_finance.processar_webhook_events" (a cada 5min)
        # drena os eventos pendentes como fallback automático.
        enqueue(processar_webhook_events_pendentes)
        log.info(
            "open_finance.webhook.enqueue_stub",
            event_id=event_id,
            pluggy_item_id=item_pluggy_id,
            nota="Celery stub: beat schedule drena eventos pendentes periodicamente",
        )
        return False
