"""Sprint 20 PR1 — Guias de pagamento LP (DARF/DARE/GPS/GRF).

Revision ID: 0052
Revises: 0051
Create Date: 2026-05-29

Tabela ``guia_pagamento``: fato imutável gerado a partir de uma apuração
fiscal (§8.2). LP paga IRPJ/CSLL/PIS/Cofins via DARF — código de receita,
valor e vencimento são determinísticos; a guia é gerada pelo sistema e o
cliente baixa + paga pelo Receita Online.

Idempotência §8.9: UNIQUE (empresa_id, competencia, codigo_receita) garante
que cada guia é gerada uma única vez por competência (re-POST retorna 409).

RLS multi-tenant §8.1: política ``guia_pagamento_tenant`` usa
``current_setting('app.tenant_id')``.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "guia_pagamento",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "empresa_id",
            UUID(as_uuid=True),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "apuracao_id",
            UUID(as_uuid=True),
            sa.ForeignKey("apuracao_fiscal.id"),
            nullable=True,
        ),
        # 'darf' | 'das' | 'gps' | 'grf' | 'dare'
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("codigo_receita", sa.String(4), nullable=False),
        sa.Column("denominacao", sa.String(100), nullable=False),
        sa.Column("competencia", sa.Date, nullable=False),
        # ex: "2026-T1" (trimestral) ou "2026-01" (mensal)
        sa.Column("periodo_apuracao", sa.String(20), nullable=False),
        sa.Column("valor_principal", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "juros", sa.Numeric(14, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "multa", sa.Numeric(14, 2), nullable=False, server_default="0"
        ),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("data_vencimento", sa.Date, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.literal_column("'a_pagar'"),
        ),
        sa.Column("pago_em", sa.Date, nullable=True),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column("fundamento_legal", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # ── RLS ──────────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE guia_pagamento ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY guia_pagamento_tenant ON guia_pagamento "
        f"USING ({_RLS_USING})"
    )

    # ── Constraints ──────────────────────────────────────────────────────────
    op.create_check_constraint(
        "ck_guia_tipo",
        "guia_pagamento",
        "tipo IN ('darf','das','gps','grf','dare')",
    )
    op.create_check_constraint(
        "ck_guia_status",
        "guia_pagamento",
        "status IN ('a_pagar','pago','cancelado')",
    )
    op.create_check_constraint(
        "ck_guia_principal_nao_negativo",
        "guia_pagamento",
        "valor_principal >= 0",
    )
    op.create_check_constraint(
        "ck_guia_total_consistente",
        "guia_pagamento",
        "total = valor_principal + juros + multa",
    )

    # ── Idempotência ─────────────────────────────────────────────────────────
    op.create_unique_constraint(
        "uq_guia_empresa_comp_receita",
        "guia_pagamento",
        ["empresa_id", "competencia", "codigo_receita"],
    )

    # ── Índices ───────────────────────────────────────────────────────────────
    op.create_index("ix_guia_tenant", "guia_pagamento", ["tenant_id"])
    op.create_index(
        "ix_guia_empresa_status",
        "guia_pagamento",
        ["empresa_id", "status"],
    )
    op.create_index(
        "ix_guia_empresa_venc",
        "guia_pagamento",
        ["empresa_id", "data_vencimento"],
    )


def downgrade() -> None:
    op.drop_table("guia_pagamento")
