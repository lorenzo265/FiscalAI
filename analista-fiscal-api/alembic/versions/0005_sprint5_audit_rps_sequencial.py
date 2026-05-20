"""Sprint 5 audit fix — RPS sequencial por empresa (CRIT-2).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-16

Background:
    A maioria das prefeituras brasileiras (com base na ABNT NBR 15032 e nas
    especificações ISS-e municipais) exige que o número de RPS seja sequencial
    contínuo por emitente. Versão anterior usava `uuid.uuid4().int[:9]`, que é
    pseudo-aleatório, sujeito a colisão (birthday paradox) e rejeitado pelo
    SEFAZ municipal.

Mudança:
    empresa.proximo_numero_rps INTEGER NOT NULL DEFAULT 1
        — contador monotônico por empresa, alocado em transação com
          SELECT ... FOR UPDATE no service de NFS-e.

Backward-compatible: coluna NOT NULL com server_default; empresas existentes
recebem 1.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column(
            "proximo_numero_rps",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("empresa", "proximo_numero_rps")
