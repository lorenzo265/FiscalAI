"""Tarefa Celery — Sincronização de NF-e via IMAP.

Sprint 2: skeleton com estrutura e pattern corretos.
Implementação completa (IMAP, MIME, attachment filter): Sprint 3.

Princípio §8.7 (AP7): tenant propagado via parâmetro explícito.
Princípio §8.9: idempotência via Redis NX para evitar duplo processamento.
"""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="ingestao.sync_imap_empresa",
    acks_late=True,
    max_retries=3,
    queue="ingestao",
)
def sync_imap_empresa(
    self: object,
    empresa_id: str,
    *,
    tenant_id: str,
) -> dict[str, object]:
    """Conecta ao IMAP configurado da empresa e ingere anexos de NF-e.

    TODO Sprint 3:
      - Buscar configuração IMAP da empresa (host, port, user, password criptografada)
      - Abrir conexão IMAP com imaplib2 ou aioimaplib
      - Filtrar emails com anexo .xml no subject "NF-e" ou "Nota Fiscal"
      - Chamar IngestaoService.ingerir_upload() para cada anexo
      - Marcar email como lido após ingestão bem-sucedida
      - Implementar idempotência via Redis SET NX (chave = empresa_id + message_uid)
    """
    log.info(
        "ingestao.imap.stub",
        empresa_id=empresa_id,
        tenant_id=tenant_id,
        nota="Implementação completa na Sprint 3",
    )
    return {"status": "noop", "empresa_id": empresa_id}
