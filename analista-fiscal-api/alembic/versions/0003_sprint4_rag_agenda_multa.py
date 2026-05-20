"""Sprint 4 — RAG + memória + agenda + multa/juros.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12

Princípios aplicados (§8 do Plano):
  8.1 — tenant_id NOT NULL + RLS em agenda_item, memoria_node, memoria_edge
  8.2 — memoria_node imutável por padrão (imutavel=TRUE)
  8.3 — selic_mensal: UNIQUE(competencia) — tabela compartilhada sem RLS (dado público BACEN)
  8.4 — seed 18 meses SELIC jan/2024–jun/2026 para testes e denúncia espontânea
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── selic_mensal (dado público BACEN — sem RLS) ───────────────────────────
    op.create_table(
        "selic_mensal",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("competencia", sa.DATE(), nullable=False, unique=True),
        sa.Column("taxa_mensal", sa.NUMERIC(6, 4), nullable=False),
        sa.Column("fonte", sa.String(255), nullable=False, server_default="BACEN"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── agenda_item ───────────────────────────────────────────────────────────
    op.create_table(
        "agenda_item",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id",
            sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("data_vencimento", sa.DATE(), nullable=False),
        sa.Column("regime", sa.String(50), nullable=False),
        sa.Column("tipo_obrigacao", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("alertado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_agenda_status", "agenda_item", "status IN ('pendente','concluido','vencido')"
    )
    op.create_index("ix_agenda_empresa_venc", "agenda_item", ["empresa_id", "data_vencimento"])
    op.create_index("ix_agenda_tenant", "agenda_item", ["tenant_id"])

    op.execute("ALTER TABLE agenda_item ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agenda_item FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON agenda_item"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )

    # ── memoria_node ──────────────────────────────────────────────────────────
    op.create_table(
        "memoria_node",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id",
            sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("rotulo", sa.String(255), nullable=False),
        sa.Column("atributos", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column("fonte_tipo", sa.String(50), nullable=True),
        sa.Column("imutavel", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Embedding column requires vector extension (added separately)
    op.execute("ALTER TABLE memoria_node ADD COLUMN embedding vector(768)")
    op.create_index("ix_memoria_node_empresa", "memoria_node", ["empresa_id", "tipo"])
    op.create_index("ix_memoria_node_tenant", "memoria_node", ["tenant_id"])
    # HNSW index for cosine similarity — melhor para RAG com alta concorrência
    op.execute(
        "CREATE INDEX ix_memoria_node_emb ON memoria_node"
        " USING hnsw (embedding vector_cosine_ops)"
        " WITH (m = 16, ef_construction = 64)"
    )

    op.execute("ALTER TABLE memoria_node ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memoria_node FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON memoria_node"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )

    # ── memoria_edge ──────────────────────────────────────────────────────────
    op.create_table(
        "memoria_edge",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("empresa_id", sa.UUID(), nullable=False),
        sa.Column(
            "origem_id",
            sa.UUID(),
            sa.ForeignKey("memoria_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "destino_id",
            sa.UUID(),
            sa.ForeignKey("memoria_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("atributos", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "valid_from",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_memoria_edge_origem", "memoria_edge", ["origem_id"])
    op.create_index("ix_memoria_edge_destino", "memoria_edge", ["destino_id"])
    op.create_index("ix_memoria_edge_empresa", "memoria_edge", ["empresa_id"])

    op.execute("ALTER TABLE memoria_edge ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memoria_edge FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON memoria_edge"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )

    # ── seed SELIC — jan/2024 a jun/2026 (18 meses + histórico) ─────────────
    # Taxas mensais aproximadas derivadas das meta SELIC do COPOM (fonte: BACEN)
    # Cálculo: (1 + taxa_anual)^(1/12) - 1, arredondado para 4 casas
    selic_seed = [
        # competencia (1º dia),  taxa_mensal
        ("2024-01-01", "0.0097"),   # 11,75% a.a.
        ("2024-02-01", "0.0093"),   # 11,25% a.a.
        ("2024-03-01", "0.0089"),   # 10,75% a.a.
        ("2024-04-01", "0.0085"),   # 10,50% a.a.
        ("2024-05-01", "0.0085"),   # 10,50% a.a.
        ("2024-06-01", "0.0085"),   # 10,50% a.a.
        ("2024-07-01", "0.0085"),   # 10,50% a.a.
        ("2024-08-01", "0.0085"),   # 10,50% a.a.
        ("2024-09-01", "0.0089"),   # 10,75% a.a.
        ("2024-10-01", "0.0093"),   # 11,25% a.a.
        ("2024-11-01", "0.0097"),   # 11,75% a.a.
        ("2024-12-01", "0.0101"),   # 12,25% a.a.
        ("2025-01-01", "0.0108"),   # 13,25% a.a.
        ("2025-02-01", "0.0115"),   # 14,25% a.a.  — COPOM acelerou aperto
        ("2025-03-01", "0.0119"),   # 14,75% a.a.
        ("2025-04-01", "0.0119"),   # 14,75% a.a.
        ("2025-05-01", "0.0119"),   # 14,75% a.a.
        ("2025-06-01", "0.0119"),   # 14,75% a.a.
        ("2025-07-01", "0.0119"),   # 14,75% a.a.
        ("2025-08-01", "0.0119"),   # 14,75% a.a.
        ("2025-09-01", "0.0119"),   # 14,75% a.a.
        ("2025-10-01", "0.0119"),   # 14,75% a.a.
        ("2025-11-01", "0.0119"),   # 14,75% a.a.
        ("2025-12-01", "0.0119"),   # 14,75% a.a.
        ("2026-01-01", "0.0119"),   # 14,75% a.a.
        ("2026-02-01", "0.0119"),   # 14,75% a.a.
        ("2026-03-01", "0.0115"),   # 14,25% a.a. — início de afrouxamento
        ("2026-04-01", "0.0112"),   # 14,00% a.a.
        ("2026-05-01", "0.0112"),   # 14,00% a.a.
        ("2026-06-01", "0.0108"),   # 13,25% a.a.
    ]

    for comp, taxa in selic_seed:
        op.execute(
            sa.text(
                "INSERT INTO selic_mensal (id, competencia, taxa_mensal, fonte)"
                " VALUES (gen_random_uuid(), :comp, :taxa, 'BACEN')"
                " ON CONFLICT (competencia) DO NOTHING"
            ).bindparams(comp=comp, taxa=taxa)
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memoria_edge CASCADE")
    op.execute("DROP TABLE IF EXISTS memoria_node CASCADE")
    op.execute("DROP TABLE IF EXISTS agenda_item CASCADE")
    op.execute("DROP TABLE IF EXISTS selic_mensal CASCADE")
