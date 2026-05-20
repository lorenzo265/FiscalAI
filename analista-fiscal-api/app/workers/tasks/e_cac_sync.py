"""Tarefa Celery — sincronização diária da caixa postal e-CAC (Sprint 6 PR3).

Skeleton com a estrutura correta. Implementação completa entra na Sprint 11
junto com o monitor RFB cadastral (§Plano linha 1145, "Status RFB diário via
SERPRO Integra Contador").

Pattern aplicado (igual à `ingestao_imap`):
  * Tarefa por empresa — tenant_id propagado explicitamente (§8.7).
  * `acks_late=True` + `max_retries=3` — perda de mensagem é pior que
    duplicação aqui (upsert idempotente em `mensagem_e_cac` por
    `id_externo_serpro`, §8.9).
  * Beat schedule: rodar 1x/dia por empresa com SerproCredencial.ativo=True
    (a definição do beat schedule fica em `celery_app.py` quando Celery for
    de fato instalado).

Fluxo previsto na implementação completa:
  1. Para cada empresa com `SerproCredencial.ativo`:
     a. Abrir async session com `SET LOCAL app.tenant_id = empresa.tenant_id`.
     b. Chamar `ECacService.sincronizar(session, tenant_id, empresa_id,
        serpro_client=app.state.serpro_client)`.
     c. Logar resultado (novas / classificadas / total_no_lote).
  2. Para mensagens classificadas como `intimacao` com prazo curto:
     a. Disparar utility template WhatsApp para o telefone cadastrado
        (`Empresa.whatsapp_phone`) usando Meta Cloud API.
     b. Inserir item na agenda (`AgendaItem`) com a data limite.

Idempotência: o próprio classificador determinístico (`classificador.py`)
não roda em mensagens já classificadas (`classificada_em IS NULL`), então
re-execuções do worker são seguras.
"""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="e_cac.sync_empresa",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def sync_e_cac_empresa(
    empresa_id: str,
    *,
    tenant_id: str,
) -> dict[str, object]:
    """Stub — implementação completa quando Celery for habilitado (Sprint 11).

    Quando habilitado, esta função vira o body de:

        @celery_app.task(
            bind=True,
            name="e_cac.sync_empresa",
            acks_late=True,
            max_retries=3,
            queue="e_cac",
        )
        def sync_e_cac_empresa(self, empresa_id, *, tenant_id): ...
    """
    log.info(
        "e_cac.sync.stub",
        empresa_id=empresa_id,
        tenant_id=tenant_id,
        nota="Beat schedule diário será ativado junto com a infra Celery (Sprint 11)",
    )
    return {"status": "noop", "empresa_id": empresa_id}
