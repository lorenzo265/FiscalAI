"""Distribuição de lucros — persiste a retenção de 10% da Lei 15.270/2025.

Revision ID: 0060
Revises: 0059
Create Date: 2026-06-21

Adiciona a coluna ``retencao_dividendos_10pct`` à tabela
``distribuicao_lucros`` para GRAVAR a retenção antecipada de 10% na fonte
(Lei 15.270/2025: dividendos > R$ 50.000/mês da mesma PJ → mesma PF,
inclusive Simples). Até aqui o valor era calculado e retornado, mas não
persistido — então o 2º+ pagamento do mês não conseguia consultar o já
retido e o service passava 0 (conservador: retinha a mais).

Com a coluna persistida, ``DistribuicaoRepo.soma_retencao_no_mes`` consulta
o já retido e o cálculo incremental fica exato.

Schema:
  * ``retencao_dividendos_10pct NUMERIC(14,2) NOT NULL DEFAULT 0``.
  * NOT NULL com ``server_default='0'`` — linhas históricas (sem retenção,
    pré-2026 ou abaixo do limite) ficam 0; seguro em uma fase.

RLS: a tabela ``distribuicao_lucros`` já tem RLS multi-tenant (policy por
``tenant_id``, migration de criação). Adicionar uma coluna NÃO altera a
policy — nenhuma mudança de RLS é necessária aqui.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "distribuicao_lucros",
        sa.Column(
            "retencao_dividendos_10pct",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("distribuicao_lucros", "retencao_dividendos_10pct")
