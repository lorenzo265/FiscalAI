"""Sprint 9 PR1 — Plano de contas hierárquico + lançamentos em partidas dobradas.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-17

Tabelas:
  conta_contabil       — Plano hierárquico (self-FK `parent_id`). SCD Type 2 via
                         `valid_from`/`valid_to`. Tipo ∈ {ativo, passivo, pl,
                         receita, despesa, conta_resultado}. Natureza D/C.
                         Apenas contas analíticas (`aceita_lancamento=true`)
                         podem aparecer em partidas.

  lancamento_contabil  — Cabeçalho. CHECK total_debito = total_credito. Origem
                         rastreável (manual|nfe|transacao|depreciacao|provisao|
                         encerramento). UNIQUE parcial em (origem_tipo, origem_id)
                         WHERE origem_id IS NOT NULL → idempotência do motor
                         automático na Sprint 9 PR2.

  partida_lancamento   — Linha. tipo ∈ {D, C}. FK conta_contabil.

Princípios aplicados (§8.1, §8.2, §8.3, §8.9).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── conta_contabil ───────────────────────────────────────────────────────
    op.create_table(
        "conta_contabil",
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
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column(
            "parent_id",
            sa.UUID(),
            sa.ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("natureza", sa.String(1), nullable=False),  # D | C
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column(
            "aceita_lancamento",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("codigo_ecd_referencial", sa.String(20), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("natureza IN ('D','C')", name="ck_conta_natureza"),
        sa.CheckConstraint(
            "tipo IN ('ativo','passivo','patrimonio_liquido','receita',"
            "'despesa','conta_resultado')",
            name="ck_conta_tipo",
        ),
        sa.CheckConstraint("nivel BETWEEN 1 AND 8", name="ck_conta_nivel"),
        sa.UniqueConstraint(
            "empresa_id", "codigo", "valid_from", name="uq_conta_codigo_vigencia"
        ),
    )
    op.create_index("ix_conta_tenant", "conta_contabil", ["tenant_id"])
    op.create_index(
        "ix_conta_empresa_codigo", "conta_contabil", ["empresa_id", "codigo"]
    )
    op.create_index(
        "ix_conta_parent", "conta_contabil", ["parent_id"]
    )
    op.execute("ALTER TABLE conta_contabil ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY conta_contabil_tenant ON conta_contabil USING ({_RLS_USING})"
    )

    # ── lancamento_contabil ──────────────────────────────────────────────────
    op.create_table(
        "lancamento_contabil",
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
        sa.Column("data_lancamento", sa.Date(), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("historico", sa.String(500), nullable=False),
        sa.Column("origem_tipo", sa.String(20), nullable=False),
        # origem_tipo ∈ {manual, nfe, transacao, depreciacao, provisao, encerramento}
        sa.Column("origem_id", sa.UUID(), nullable=True),
        sa.Column("total_debito", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_credito", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="rascunho"
        ),
        # status ∈ {rascunho, confirmado, encerrado}
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
            "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
            "'provisao','encerramento','ajuste')",
            name="ck_lanc_origem_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('rascunho','confirmado','encerrado')",
            name="ck_lanc_status",
        ),
        sa.CheckConstraint(
            "total_debito = total_credito", name="ck_lanc_partidas_dobradas"
        ),
        sa.CheckConstraint(
            "total_debito >= 0", name="ck_lanc_totais_nao_negativos"
        ),
    )
    op.create_index("ix_lanc_tenant", "lancamento_contabil", ["tenant_id"])
    op.create_index(
        "ix_lanc_empresa_comp",
        "lancamento_contabil",
        ["empresa_id", "competencia"],
    )
    op.create_index(
        "ix_lanc_empresa_data",
        "lancamento_contabil",
        ["empresa_id", "data_lancamento"],
    )
    # UNIQUE parcial — idempotência do motor automático (PR2)
    op.create_index(
        "uq_lanc_origem",
        "lancamento_contabil",
        ["origem_tipo", "origem_id"],
        unique=True,
        postgresql_where=sa.text("origem_id IS NOT NULL"),
    )
    op.execute("ALTER TABLE lancamento_contabil ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY lancamento_contabil_tenant ON lancamento_contabil USING ({_RLS_USING})"
    )

    # ── partida_lancamento ───────────────────────────────────────────────────
    op.create_table(
        "partida_lancamento",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "lancamento_id",
            sa.UUID(),
            sa.ForeignKey("lancamento_contabil.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conta_contabil_id",
            sa.UUID(),
            sa.ForeignKey("conta_contabil.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(1), nullable=False),  # D | C
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tipo IN ('D','C')", name="ck_partida_tipo"),
        sa.CheckConstraint("valor > 0", name="ck_partida_valor_positivo"),
    )
    op.create_index(
        "ix_partida_lanc", "partida_lancamento", ["lancamento_id", "ordem"]
    )
    op.create_index(
        "ix_partida_conta", "partida_lancamento", ["conta_contabil_id"]
    )
    op.execute("ALTER TABLE partida_lancamento ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY partida_lancamento_tenant ON partida_lancamento USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS partida_lancamento_tenant ON partida_lancamento"
    )
    op.drop_table("partida_lancamento")
    op.execute(
        "DROP POLICY IF EXISTS lancamento_contabil_tenant ON lancamento_contabil"
    )
    op.drop_table("lancamento_contabil")
    op.execute(
        "DROP POLICY IF EXISTS conta_contabil_tenant ON conta_contabil"
    )
    op.drop_table("conta_contabil")
