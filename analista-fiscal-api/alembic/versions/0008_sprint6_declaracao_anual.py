"""Sprint 6 PR3 — DEFIS + DASN-SIMEI (declarações anuais).

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-17

Modela ``declaracao_anual`` cobrindo dois tipos:
  DEFIS       — Declaração de Informações Socioeconômicas e Fiscais (SN).
                Anexa ao PGDAS-D, exigida até 31/março do ano seguinte.
  DASN_SIMEI  — Declaração Anual do Simples Nacional - MEI.
                Receita bruta + flag de empregado, até 31/maio do ano seguinte.

Princípios aplicados (§8.1, §8.2, §8.9).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "declaracao_anual",
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
        sa.Column("tipo", sa.String(20), nullable=False),
        # tipo ∈ {DEFIS, DASN_SIMEI}
        sa.Column("ano_base", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        # status ∈ {gerada, transmitida, erro}
        sa.Column("payload_json", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("algoritmo_versao", sa.String(20), nullable=False),
        sa.Column("protocolo", sa.String(60), nullable=True),
        sa.Column("transmitida_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("recibo_pdf_storage_key", sa.String(500), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("serpro_chamada_id", sa.UUID(), nullable=True),
        sa.Column("erro_codigo", sa.String(80), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "atualizado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('DEFIS','DASN_SIMEI')",
            name="ck_declaracao_anual_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('gerada','transmitida','erro')",
            name="ck_declaracao_anual_status",
        ),
        sa.CheckConstraint(
            "ano_base BETWEEN 2018 AND 2099",
            name="ck_declaracao_anual_ano",
        ),
        sa.UniqueConstraint(
            "empresa_id",
            "tipo",
            "ano_base",
            name="uq_declaracao_anual_empresa_tipo_ano",
        ),
    )
    op.create_index("ix_declaracao_anual_tenant", "declaracao_anual", ["tenant_id"])
    op.create_index(
        "ix_declaracao_anual_empresa_ano",
        "declaracao_anual",
        ["empresa_id", "ano_base"],
    )
    op.execute("ALTER TABLE declaracao_anual ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY declaracao_anual_tenant ON declaracao_anual USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS declaracao_anual_tenant ON declaracao_anual")
    op.drop_table("declaracao_anual")
