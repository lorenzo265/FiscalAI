"""Sprint 12 PR1 — tabela ``relatorio_gerado`` (snapshot imutável).

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-17

Tabela única reusada por DRE/Balanço/DFC/Indicadores. Snapshot imutável
do balancete consolidado do período (§8.2) — recálculos geram nova linha
com ``superseded_by`` apontando para a anterior, preservando histórico.

Modelo simples:
  * 1 linha por (empresa, tipo, periodo_inicio, periodo_fim) **ativa**
    — UNIQUE parcial onde ``superseded_by IS NULL``.
  * ``payload`` JSONB carrega a estrutura hierárquica do relatório.
  * ``saldos_base`` JSONB é o snapshot dos saldos contábeis usados como
    input — permite auditoria e re-cálculo determinístico.

Princípios: §8.1 (RLS), §8.2 (imutável), §8.9 (UNIQUE parcial).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "relatorio_gerado",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=False),
        sa.Column("periodo_fim", sa.Date(), nullable=False),
        sa.Column(
            "payload", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        sa.Column(
            "saldos_base", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "superseded_by", sa.UUID(),
            sa.ForeignKey("relatorio_gerado.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('dre','balanco','dfc','indicadores','dre_aux_lp')",
            name="ck_relatorio_tipo",
        ),
        sa.CheckConstraint(
            "periodo_fim >= periodo_inicio",
            name="ck_relatorio_periodo_coerente",
        ),
    )
    op.create_index("ix_relatorio_tenant", "relatorio_gerado", ["tenant_id"])
    op.create_index(
        "ix_relatorio_empresa_tipo", "relatorio_gerado",
        ["empresa_id", "tipo", "periodo_inicio"],
    )
    # UNIQUE parcial: apenas 1 ativo por (empresa, tipo, periodo).
    op.create_index(
        "uq_relatorio_ativo", "relatorio_gerado",
        ["empresa_id", "tipo", "periodo_inicio", "periodo_fim"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute("ALTER TABLE relatorio_gerado ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY relatorio_gerado_tenant ON relatorio_gerado "
        f"USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS relatorio_gerado_tenant ON relatorio_gerado")
    op.drop_table("relatorio_gerado")
