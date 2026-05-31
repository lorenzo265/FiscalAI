"""Fase 2 PR9 — flag ``aliquota_iss_validada`` na empresa (MINOR m5).

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-21

Auditoria das Sprints 4-6 apontou que ``_AVISO_ISS`` em ``app/modules/notas/service.py``
é retornado em TODA emissão de NFS-e. Vira ruído após o contador validar a alíquota
uma vez. Adicionamos flag por empresa: aviso só vai enquanto ``aliquota_iss_validada
= false``. PATCH ``/v1/empresas/{eid}`` (existente) ou novo endpoint manual aceita
``aliquota_iss_validada=true`` para confirmar.

Nullable=False com server_default false — empresas existentes recebem ``false``,
exibem o aviso até validação manual (comportamento idêntico ao pré-fix).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column(
            "aliquota_iss_validada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("empresa", "aliquota_iss_validada")
