"""Sprint 8 PR2 — provisões trabalhistas mensais.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-17

Tabela ``provisao_mensal``:
  * Uma linha por (empresa, competência, tipo[, funcionario_id]).
  * `funcionario_id` é nullable — null indica provisão agregada por empresa.
    O módulo de pessoal (Sprint 10) traz folha individual; até lá usamos
    apenas agregado por `folha_mes_total`.
  * UNIQUE composto garante idempotência do worker mensal (§8.9). Quando
    `funcionario_id` é NULL, usamos um índice único parcial.

Tipos cobertos:
  ferias        — 1/12 da folha + 1/3 constitucional sobre o 1/12
  13_salario    — 1/12 da folha
  inss_ferias   — INSS patronal sobre provisão de férias (20% LP / 0 SN-MEI)
  inss_13       — INSS patronal sobre provisão de 13º
  fgts_ferias   — FGTS 8% sobre provisão de férias
  fgts_13       — FGTS 8% sobre provisão de 13º

Princípios aplicados (§8.1, §8.2, §8.9).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "provisao_mensal",
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
        sa.Column("funcionario_id", sa.UUID(), nullable=True),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("base_calculo", sa.Numeric(14, 2), nullable=False),
        sa.Column("aliquota", sa.Numeric(6, 4), nullable=False),
        sa.Column("valor_provisao", sa.Numeric(14, 2), nullable=False),
        sa.Column("algoritmo_versao", sa.String(20), nullable=False),
        sa.Column("lancamento_contabil_id", sa.UUID(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('ferias','13_salario','inss_ferias','inss_13',"
            "'fgts_ferias','fgts_13')",
            name="ck_provisao_tipo",
        ),
        sa.CheckConstraint(
            "base_calculo >= 0 AND valor_provisao >= 0 AND aliquota >= 0",
            name="ck_provisao_valores_nao_negativos",
        ),
    )
    op.create_index(
        "ix_provisao_empresa_comp", "provisao_mensal", ["empresa_id", "competencia", "tipo"]
    )
    op.create_index("ix_provisao_tenant", "provisao_mensal", ["tenant_id"])
    # UNIQUE parcial para provisão agregada (funcionario_id IS NULL).
    op.create_index(
        "uq_provisao_agregada",
        "provisao_mensal",
        ["empresa_id", "competencia", "tipo"],
        unique=True,
        postgresql_where=sa.text("funcionario_id IS NULL"),
    )
    # UNIQUE parcial para provisão individual.
    op.create_index(
        "uq_provisao_individual",
        "provisao_mensal",
        ["empresa_id", "competencia", "tipo", "funcionario_id"],
        unique=True,
        postgresql_where=sa.text("funcionario_id IS NOT NULL"),
    )
    op.execute("ALTER TABLE provisao_mensal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY provisao_mensal_tenant ON provisao_mensal USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS provisao_mensal_tenant ON provisao_mensal"
    )
    op.drop_table("provisao_mensal")
