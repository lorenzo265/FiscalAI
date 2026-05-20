"""Tarefa Celery — provisão trabalhista mensal (Sprint 8 PR2).

Skeleton com pattern correto. Implementação completa quando Celery for ativado
(Sprint 11).

Fluxo previsto:
  1. Beat schedule: último dia útil de cada mês.
  2. Para cada empresa com folha registrada (Sprint 10):
     a. SET LOCAL app.tenant_id.
     b. Calcula folha agregada do mês.
     c. ProvisoesService.gerar_provisao_mensal(competencia, folha).
  3. Logar resultado (linhas geradas, valor total).

Trigger manual hoje:
  ``POST /v1/empresas/{id}/provisoes/{AAAA-MM}`` com folha_mes_total no body.
"""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="provisoes.gerar_provisao_empresa",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_provisao_empresa(
    empresa_id: str,
    competencia: str,
    folha_mes_total: str,
    *,
    tenant_id: str,
) -> dict[str, object]:
    """Stub — vira task Celery quando o pacote for instalado (Sprint 11)."""
    log.info(
        "provisoes.stub",
        empresa_id=empresa_id,
        competencia=competencia,
        folha=folha_mes_total,
        tenant_id=tenant_id,
        nota="Beat schedule ativado junto com a infra Celery (Sprint 11)",
    )
    return {"status": "noop", "empresa_id": empresa_id}
