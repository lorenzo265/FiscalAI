"""Sprint 15.5 PR1 — Auditoria de envio do digest WhatsApp.

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-24

Adiciona colunas para rastreamento do envio do digest via Meta WhatsApp
template (Sprint 15.5):

  * ``tentativas_envio`` — contador de tentativas (incrementado a cada
    falha; após 5 → ``status='falhou'``).
  * ``ultimo_erro_envio`` — última mensagem de erro truncada a 500 chars.
  * ``enviado_template_name`` — nome do template Meta usado (auditoria).

Estende o CHECK do ``status`` para incluir ``falhou``:

  Antes: ``status ∈ {preparado, enviado, cancelado}``
  Depois: ``status ∈ {preparado, enviado, cancelado, falhou}``

Migration backward-compatible (adiciona colunas nullable / com default;
CHECK substituído atomicamente via DROP + ADD no mesmo transaction). Não
precisa de 2 fases — colunas novas não bloqueiam código existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "digest_semanal",
        sa.Column(
            "tentativas_envio", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "digest_semanal",
        sa.Column("ultimo_erro_envio", sa.Text(), nullable=True),
    )
    op.add_column(
        "digest_semanal",
        sa.Column("enviado_template_name", sa.String(60), nullable=True),
    )
    op.create_check_constraint(
        "ck_digest_tentativas_positivas",
        "digest_semanal",
        "tentativas_envio >= 0",
    )
    # Estende CHECK do status para incluir 'falhou'.
    op.drop_constraint(
        "ck_digest_status", "digest_semanal", type_="check"
    )
    op.create_check_constraint(
        "ck_digest_status",
        "digest_semanal",
        "status IN ('preparado','enviado','cancelado','falhou')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_digest_status", "digest_semanal", type_="check"
    )
    op.create_check_constraint(
        "ck_digest_status",
        "digest_semanal",
        "status IN ('preparado','enviado','cancelado')",
    )
    op.drop_constraint(
        "ck_digest_tentativas_positivas", "digest_semanal", type_="check"
    )
    op.drop_column("digest_semanal", "enviado_template_name")
    op.drop_column("digest_semanal", "ultimo_erro_envio")
    op.drop_column("digest_semanal", "tentativas_envio")
