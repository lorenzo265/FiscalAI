"""Tarefa Celery — depreciação mensal automática (Sprint 8 PR1, IN SRF 162/1998).

Skeleton com pattern correto. Implementação completa quando Celery for ativado
(Sprint 11).

Pattern aplicado (igual a ``e_cac_sync``):
  * Tarefa por empresa — ``tenant_id`` propagado explicitamente (§8.7).
  * Idempotência garantida por UNIQUE (bem_id, competencia) em
    ``depreciacao_mensal``.

Fluxo previsto:
  1. Beat schedule: 1º dia útil de cada mês.
  2. Para cada empresa com bens imobilizados ativos:
     a. Abrir sessão com SET LOCAL app.tenant_id.
     b. Chamar ``ImobilizadoService.gerar_depreciacao_mensal(competencia_anterior)``.
     c. Logar resultado (bens processados, valor total).

Trigger manual hoje:
  ``POST /v1/empresas/{id}/imobilizado/depreciacao/{AAAA-MM}``.
"""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="imobilizado.gerar_depreciacao_empresa",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_depreciacao_empresa(
    empresa_id: str,
    competencia: str,
    *,
    tenant_id: str,
) -> dict[str, object]:
    """Stub — vira task Celery quando o pacote for instalado (Sprint 11)."""
    log.info(
        "imobilizado.depreciacao.stub",
        empresa_id=empresa_id,
        competencia=competencia,
        tenant_id=tenant_id,
        nota="Beat schedule ativado junto com a infra Celery (Sprint 11)",
    )
    return {"status": "noop", "empresa_id": empresa_id}
