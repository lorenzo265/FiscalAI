"""Sprint 9 PR3 — saldos mensais materializados + encerramento.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-17

Tabela ``saldo_conta_mes``:
  * Materialização do balancete por (empresa, conta, competencia).
  * Populada pelo serviço de encerramento mensal.
  * UNIQUE (empresa, conta, competencia) → idempotência.
  * ``status='aberto'`` enquanto o mês ainda pode receber lançamentos;
    ``status='fechado'`` após encerramento — bloqueia novos lançamentos
    nessa competência (regra reforçada no service).

Encerramento mensal NÃO cria nova tabela — apenas:
  1. UPDATE lancamento_contabil SET status='encerrado' WHERE competencia=X.
  2. INSERT em saldo_conta_mes.

Encerramento anual gera 1 lançamento de apuração que zera contas de
receita/despesa contra ``3.9.01 Resultado do Exercício``.

Princípios aplicados (§8.1, §8.2).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "saldo_conta_mes",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id",
            sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conta_contabil_id",
            sa.UUID(),
            sa.ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("saldo_inicial", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_debitos", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_creditos", sa.Numeric(14, 2), nullable=False),
        sa.Column("saldo_final", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="fechado"),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('aberto','fechado')", name="ck_saldo_status"
        ),
        sa.UniqueConstraint(
            "empresa_id",
            "conta_contabil_id",
            "competencia",
            name="uq_saldo_empresa_conta_comp",
        ),
    )
    op.create_index("ix_saldo_tenant", "saldo_conta_mes", ["tenant_id"])
    op.create_index(
        "ix_saldo_empresa_comp", "saldo_conta_mes", ["empresa_id", "competencia"]
    )
    op.execute("ALTER TABLE saldo_conta_mes ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY saldo_conta_mes_tenant ON saldo_conta_mes USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS saldo_conta_mes_tenant ON saldo_conta_mes"
    )
    op.drop_table("saldo_conta_mes")
