"""Tarefa Celery — sync Pluggy + processamento de webhook events (Sprint 7 PR2).

Skeleton — implementação completa quando a infra Celery for ativada (Sprint 11).

Pattern aplicado (igual a ``ingestao_imap`` e ``e_cac_sync``):
  * Tarefa por empresa — ``tenant_id`` propagado explicitamente (§8.7).
  * ``acks_late=True`` + ``max_retries=3``.
  * Idempotência garantida pelos UPSERTs em
    ``conta_bancaria.pluggy_account_id`` e
    ``transacao_bancaria.pluggy_transaction_id``.

Fluxo previsto:
  1. Beat schedule diário — lista empresas com PluggyItem ativo
     (``status='LOGIN_SUCCEEDED'``).
  2. Para cada empresa:
     a. Abrir sessão com SET LOCAL app.tenant_id.
     b. Chamar ``SyncService.sincronizar_item`` para cada item.
     c. Logar resultado (contas / transações processadas).
  3. Fluxo paralelo: processar ``pluggy_webhook_event`` com
     ``processado=false`` (admin role, cross-tenant lookup permitido) →
     dispara ``SyncService`` no tenant correto.

Trigger manual hoje: ``POST /v1/empresas/{id}/open-finance/items/{item_uuid}/sync``.
"""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="open_finance.sync_pluggy_empresa",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def sync_pluggy_empresa(
    empresa_id: str,
    *,
    tenant_id: str,
) -> dict[str, object]:
    """Stub — vira task Celery quando o pacote for instalado (Sprint 11)."""
    log.info(
        "open_finance.sync_pluggy.stub",
        empresa_id=empresa_id,
        tenant_id=tenant_id,
        nota="Worker ativado junto com a infra Celery (Sprint 11)",
    )
    return {"status": "noop", "empresa_id": empresa_id}


@celery_app.task(
    name="open_finance.processar_webhook_events",
    acks_late=True,
    queue="default",
)
def processar_webhook_events_pendentes() -> dict[str, object]:
    """Stub — drena ``pluggy_webhook_event`` com ``processado=false``.

    Em produção: lê com role admin (bypass de RLS), faz routing por
    ``pluggy_item_id`` → tenant_id, dispara ``SyncService`` em sessão
    com ``SET LOCAL app.tenant_id`` adequado.
    """
    log.info(
        "open_finance.processar_webhook.stub",
        nota="Drain de webhook events fica para Sprint 11",
    )
    return {"status": "noop"}
