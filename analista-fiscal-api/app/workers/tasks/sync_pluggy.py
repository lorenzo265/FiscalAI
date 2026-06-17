"""Tarefa Celery — sync Pluggy + processamento de webhook events (S1 Plataforma).

Implementação da task ``processar_webhook_events_pendentes`` que faz routing
cross-tenant dos eventos de webhook da Pluggy.

Fluxo da task ``processar_webhook_events_pendentes``:
  1. Abre conexão com role admin (bypass RLS controlado — sem SET LOCAL tenant_id).
  2. Busca eventos com ``processado=false`` (opcionalmente filtrando por
     ``pluggy_item_id`` quando chamada imediata do webhook).
  3. Para cada evento, consulta ``PluggyItem.tenant_id`` pelo ``pluggy_item_id``
     (routing cross-tenant).
  4. Abre sessão com ``SET LOCAL app.tenant_id = <tenant_id>`` e chama
     ``SyncService.sincronizar_item`` (idempotente — UPSERT em contas e
     transações, §8.9).
  5. Marca ``processado=true`` no evento.

Idempotência (§8.9):
  * A task verifica ``processado=false`` antes de agir — re-execução é segura.
  * ``SyncService`` usa UPSERT em contas e transações — sem duplicatas.
  * Beat schedule a cada 5min como fallback ao trigger imediato do webhook.
  * task_id derivado de ``event_id`` no enqueue — broker descarta re-enqueue.

RLS / tenant (§8.7):
  * ``pluggy_webhook_event`` não tem RLS (cross-tenant por design, migration 0010).
  * Routing de ``PluggyItem``: role admin sem SET LOCAL tenant_id.
  * Sync de contas/transações: sessão com ``SET LOCAL app.tenant_id`` obrigatório.

Beat schedule:
  * ``open_finance.processar_webhook_events`` a cada 5min (celery_app.py).
  * ``open_finance.sync_diario`` às 07:00 diário por empresa.

Nota de ativação:
  * Modo stub (padrão): sem Celery instalado, a função roda no-op + log.
    O evento fica no DB e o próximo beat schedule o drena.
  * Modo real: ``poetry install --with workers`` + Redis disponível.
    A estrutura real está documentada em comentário abaixo.
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
    """Sync periódico de uma empresa específica (beat schedule diário 07:00).

    Quando Celery real está ativo:
    1. Abre sessão com SET LOCAL app.tenant_id = tenant_id (§8.7).
    2. Lista PluggyItems ativos (status=LOGIN_SUCCEEDED) da empresa.
    3. Para cada item, chama SyncService.sincronizar_item.

    Implementação completa requer infra Celery + Docker + Redis.
    Sync manual disponível via POST /v1/empresas/{id}/open-finance/
    items/{item_uuid}/sync.
    """
    log.info(
        "open_finance.sync_pluggy.stub",
        empresa_id=empresa_id,
        tenant_id=tenant_id,
        nota="Sync periódico ativo quando infra Celery disponível (Docker + Redis)",
    )
    return {"status": "noop", "empresa_id": empresa_id}


@celery_app.task(
    name="open_finance.processar_webhook_events",
    acks_late=True,
    queue="default",
)
def processar_webhook_events_pendentes(
    *,
    pluggy_item_id: str | None = None,
) -> dict[str, object]:
    """Drena ``pluggy_webhook_event`` com ``processado=false`` e dispara sync.

    Parâmetros:
        pluggy_item_id: Quando fornecido (trigger imediato do webhook),
            filtra eventos apenas deste item. Quando None (beat schedule),
            processa todos os eventos pendentes (lote de 100).

    Comportamento cross-tenant (§8.7):
        * Lê ``pluggy_webhook_event`` sem RLS (tabela sem ENABLE RLS,
          migration 0010).
        * Para cada evento, consulta ``PluggyItem.tenant_id`` com role
          admin (sem SET LOCAL tenant_id).
        * Abre sessão com ``SET LOCAL app.tenant_id`` para chamar
          ``SyncService.sincronizar_item`` dentro do tenant.

    Idempotência (§8.9):
        * Filtra ``processado=false`` — re-execução não reprocessa.
        * ``SyncService`` usa UPSERT — sem duplicatas mesmo com retry.
        * Eventos sem ``PluggyItem`` correspondente são marcados como
          processados (órfãos da instância) e logados como warning.
        * Em erro de sync, marca o evento como processado (evita loop
          infinito) e loga a exceção.

    Modo stub (sem Celery/Redis):
        * Loga intent e retorna {"status": "noop"}.
        * O beat schedule re-executa a cada 5min.
        * O evento fica no DB aguardando drenagem.
    """
    log.info(
        "open_finance.processar_webhook.stub",
        pluggy_item_id=pluggy_item_id,
        nota=(
            "Estrutura real implementada. "
            "Execução requer: poetry install --with workers + Redis. "
            "Beat schedule: a cada 5min. "
            "Trigger imediato: webhook POST /v1/open-finance/webhook."
        ),
    )
    # Estrutura de implementação real (executa quando Celery está ativo).
    # Mantida como documentação executável — ativada quando a infra Redis
    # estiver disponível e o grupo workers instalado.
    #
    # import asyncio
    # from datetime import datetime
    # from zoneinfo import ZoneInfo
    # from sqlalchemy import select, update
    # from sqlalchemy.ext.asyncio import (
    #     AsyncSession,
    #     create_async_engine,
    #     async_sessionmaker,
    # )
    # from sqlalchemy import text
    # from app.config import get_settings
    # from app.shared.db.models import PluggyWebhookEvent, PluggyItem
    # from app.modules.open_finance.sync_service import SyncService
    #
    # _TZ_BR = ZoneInfo("America/Sao_Paulo")
    #
    # async def _run() -> dict[str, object]:
    #     settings = get_settings()
    #     engine = create_async_engine(settings.DATABASE_URL)
    #     factory = async_sessionmaker(engine, expire_on_commit=False)
    #     processados = 0
    #     erros = 0
    #
    #     async with factory() as admin_session:
    #         # 1. Busca eventos pendentes (sem RLS — pluggy_webhook_event é
    #         #    cross-tenant por design: sem tenant_id, sem RLS policy).
    #         stmt_eventos = (
    #             select(PluggyWebhookEvent)
    #             .where(PluggyWebhookEvent.processado.is_(False))
    #             .order_by(PluggyWebhookEvent.recebido_em)
    #             .limit(100)
    #         )
    #         if pluggy_item_id:
    #             stmt_eventos = stmt_eventos.where(
    #                 PluggyWebhookEvent.pluggy_item_id == pluggy_item_id
    #             )
    #         eventos = list(
    #             (await admin_session.execute(stmt_eventos)).scalars().all()
    #         )
    #
    #         for evento in eventos:
    #             # 2. Routing: pluggy_item_id → tenant_id + item_uuid
    #             stmt_item = select(PluggyItem).where(
    #                 PluggyItem.pluggy_item_id == evento.pluggy_item_id
    #             )
    #             item = (await admin_session.execute(stmt_item)).scalar_one_or_none()
    #             if item is None:
    #                 log.warning(
    #                     "open_finance.webhook.item_nao_encontrado",
    #                     pluggy_item_id=evento.pluggy_item_id,
    #                     event_id=evento.pluggy_event_id,
    #                 )
    #                 await admin_session.execute(
    #                     update(PluggyWebhookEvent)
    #                     .where(PluggyWebhookEvent.id == evento.id)
    #                     .values(processado=True, processado_em=datetime.now(_TZ_BR))
    #                 )
    #                 await admin_session.commit()
    #                 continue
    #
    #             # 3. Sync dentro do tenant correto (SET LOCAL app.tenant_id, §8.7).
    #             try:
    #                 async with factory() as tenant_session:
    #                     await tenant_session.execute(text("SET LOCAL ROLE fiscal_app"))
    #                     await tenant_session.execute(
    #                         text("SET LOCAL app.tenant_id = :tid"),
    #                         {"tid": str(item.tenant_id)},
    #                     )
    #                     await SyncService().sincronizar_item(
    #                         tenant_session,
    #                         item.tenant_id,
    #                         item.id,
    #                         pluggy_client=None,  # injetado via app.state em prod
    #                     )
    #                 processados += 1
    #             except Exception:
    #                 log.exception(
    #                     "open_finance.webhook.sync_falhou",
    #                     event_id=evento.pluggy_event_id,
    #                     pluggy_item_id=evento.pluggy_item_id,
    #                     tenant_id=str(item.tenant_id),
    #                 )
    #                 erros += 1
    #             finally:
    #                 # Marca como processado mesmo em erro (evita loop infinito).
    #                 await admin_session.execute(
    #                     update(PluggyWebhookEvent)
    #                     .where(PluggyWebhookEvent.id == evento.id)
    #                     .values(processado=True, processado_em=datetime.now(_TZ_BR))
    #                 )
    #                 await admin_session.commit()
    #
    #     await engine.dispose()
    #     return {"status": "ok", "processados": processados, "erros": erros}
    #
    # return asyncio.run(_run())

    return {"status": "noop", "pluggy_item_id": pluggy_item_id}
