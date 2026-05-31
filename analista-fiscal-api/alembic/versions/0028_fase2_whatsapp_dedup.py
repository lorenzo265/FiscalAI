"""Fase 2 PR7 — dedup de ``mensagem_id`` do webhook Meta WhatsApp (MAJOR M1).

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-21

Auditoria das Sprints 4-6 identificou que ``app/modules/whatsapp/router.py``
recebe ``mensagem_id`` no payload mas **não faz dedup**. Meta Cloud API faz
retry em 5xx/timeout → mesma mensagem processa N vezes:

  * ``sessao.mensagens_na_sessao`` infla, rompendo o limite UX de 3 antes do
    tempo (CLAUDE.md UX rule).
  * ``sender.enviar_texto`` é chamado 2x → usuário recebe resposta duplicada.

Tabela ``whatsapp_mensagem_processada``:
  * ``mensagem_id`` (PK) — ID retornado pelo Meta no campo ``messages[].id``;
    string opaca, garantida única por Meta.
  * Sem RLS — rota de sistema (mesma estratégia de ``pluggy_webhook_event``);
    a checagem é atômica via ``INSERT ... ON CONFLICT DO NOTHING``.
  * ``processed_at`` com índice — task Celery diária (``whatsapp.expurgar_processadas``)
    apaga linhas > 7 dias (Meta documenta que retries não persistem além disso).
  * REVOKE UPDATE/DELETE FROM PUBLIC — append-only por design (§8.2 + §8.9).

Princípios aplicados: §8.9 (idempotência cravada em DB) + §8.2 (registro
imutável da mensagem processada — útil para auditoria de fluxo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_mensagem_processada",
        sa.Column("mensagem_id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id",
            sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_whatsapp_msg_processed_at",
        "whatsapp_mensagem_processada",
        ["processed_at"],
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON whatsapp_mensagem_processada FROM PUBLIC"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_whatsapp_msg_processed_at", table_name="whatsapp_mensagem_processada"
    )
    op.drop_table("whatsapp_mensagem_processada")
