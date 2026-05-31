"""Fase 2 PR10 — precisão da alíquota persistida em ``provisao_mensal``.

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-21

Problema: ``provisao_mensal.aliquota`` é ``NUMERIC(6,4)``. O algoritmo persiste
``Decimal("0.0833")`` arredondado enquanto calcula ``Decimal(1)/Decimal(12)``
exato. Auditor que multiplique ``base_calculo × aliquota_persistida`` acha
discrepância de ~R$ 0,03 em folha de R$ 10k.

Solução: ampliar a coluna para ``NUMERIC(8,6)`` (6 casas decimais).
Cast amplia precisão sem perda — registros antigos (``0.0833``) ficam como
``0.083300`` e seguem coerentes.

Princípio §8.10 (observabilidade): auditoria visual da alíquota persistida
agora bate com o cálculo a 6 casas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "provisao_mensal",
        "aliquota",
        existing_type=sa.NUMERIC(6, 4),
        type_=sa.NUMERIC(8, 6),
        existing_nullable=False,
        postgresql_using="aliquota::NUMERIC(8,6)",
    )


def downgrade() -> None:
    op.alter_column(
        "provisao_mensal",
        "aliquota",
        existing_type=sa.NUMERIC(8, 6),
        type_=sa.NUMERIC(6, 4),
        existing_nullable=False,
        postgresql_using="aliquota::NUMERIC(6,4)",
    )
