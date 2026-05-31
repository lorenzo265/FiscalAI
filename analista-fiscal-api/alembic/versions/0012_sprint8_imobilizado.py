"""Sprint 8 PR1 — Imobilizado + depreciação automática (IN SRF 162/1998).

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-17

Tabelas:
  tabela_depreciacao_rfb  — SCD Type 2. Seed com 6 categorias do anexo I
                            da IN SRF 162/1998. Sem tenant_id (referência
                            pública).

  bem_imobilizado         — Cadastro de ativos da empresa. FK opcional para
                            documento_fiscal quando o bem veio de NF de
                            entrada (Sprint 2). Trilha `data_baixa` para
                            encerramento contábil.

  depreciacao_mensal      — Linha por (bem, competência). UNIQUE garante
                            idempotência do worker mensal (§8.9). Append-only
                            (§8.2).

Princípios aplicados (§8.1, §8.2, §8.3, §8.9).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"

# Seed IN SRF 162/1998 anexo I — vigência 01/01/1999.
_SEED_DEPRECIACAO_RFB = [
    # (categoria, taxa_anual, vida_util_anos)
    ("imovel", "0.0400", 25),
    ("edificacao", "0.0400", 25),
    ("veiculo", "0.2000", 5),
    ("maquina", "0.1000", 10),
    ("computador", "0.2000", 5),
    ("movel", "0.1000", 10),
]


def upgrade() -> None:
    # ── tabela_depreciacao_rfb ───────────────────────────────────────────────
    op.create_table(
        "tabela_depreciacao_rfb",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("categoria", sa.String(40), nullable=False),
        sa.Column("taxa_anual", sa.Numeric(6, 4), nullable=False),
        sa.Column("vida_util_anos", sa.Integer(), nullable=False),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_tabela_depreciacao_categoria_vigencia",
        "tabela_depreciacao_rfb",
        ["categoria", "valid_from", "valid_to"],
    )

    # Seed
    for categoria, taxa, vida in _SEED_DEPRECIACAO_RFB:
        op.execute(
            sa.text(
                "INSERT INTO tabela_depreciacao_rfb "
                "(id, categoria, taxa_anual, vida_util_anos, fonte, valid_from) "
                "VALUES (gen_random_uuid(), :cat, :taxa, :vida, :fonte, :vf)"
            ).bindparams(
                sa.bindparam("cat", categoria, type_=sa.String(50)),
                sa.bindparam("taxa", taxa, type_=sa.Numeric(6, 4)),
                sa.bindparam("vida", vida, type_=sa.Integer()),
                sa.bindparam("fonte", "IN SRF 162/1998 anexo I", type_=sa.String(255)),
                sa.bindparam("vf", "1999-01-01", type_=sa.Date()),
            )
        )

    # ── bem_imobilizado ──────────────────────────────────────────────────────
    op.create_table(
        "bem_imobilizado",
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
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("categoria", sa.String(40), nullable=False),
        sa.Column("data_aquisicao", sa.Date(), nullable=False),
        sa.Column("valor_aquisicao", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "documento_fiscal_id",
            sa.UUID(),
            sa.ForeignKey("documento_fiscal.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conta_contabil_id", sa.UUID(), nullable=True),
        sa.Column("taxa_depreciacao_anual", sa.Numeric(6, 4), nullable=False),
        sa.Column(
            "metodo_depreciacao",
            sa.String(20),
            nullable=False,
            server_default="linear",
        ),
        sa.Column("vida_util_meses", sa.Integer(), nullable=False),
        sa.Column(
            "valor_residual",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("data_baixa", sa.Date(), nullable=True),
        sa.Column("motivo_baixa", sa.String(255), nullable=True),
        sa.Column(
            "ativo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
            "categoria IN ('imovel','edificacao','veiculo','maquina',"
            "'computador','movel','outro')",
            name="ck_bem_categoria",
        ),
        sa.CheckConstraint(
            "metodo_depreciacao IN ('linear','soma_digitos','unidades_produzidas')",
            name="ck_bem_metodo",
        ),
        sa.CheckConstraint(
            "valor_aquisicao > 0", name="ck_bem_valor_positivo"
        ),
        sa.CheckConstraint(
            "vida_util_meses > 0", name="ck_bem_vida_util_positiva"
        ),
        sa.CheckConstraint(
            "valor_residual >= 0 AND valor_residual <= valor_aquisicao",
            name="ck_bem_residual_valido",
        ),
    )
    op.create_index("ix_bem_imob_tenant", "bem_imobilizado", ["tenant_id"])
    op.create_index(
        "ix_bem_imob_empresa_ativo",
        "bem_imobilizado",
        ["empresa_id"],
        postgresql_where=sa.text("ativo IS TRUE AND data_baixa IS NULL"),
    )
    op.execute("ALTER TABLE bem_imobilizado ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY bem_imobilizado_tenant ON bem_imobilizado USING ({_RLS_USING})"
    )

    # ── depreciacao_mensal ───────────────────────────────────────────────────
    op.create_table(
        "depreciacao_mensal",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "bem_id",
            sa.UUID(),
            sa.ForeignKey("bem_imobilizado.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("valor_depreciado", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_acumulado", sa.Numeric(14, 2), nullable=False),
        sa.Column("saldo_contabil", sa.Numeric(14, 2), nullable=False),
        sa.Column("lancamento_contabil_id", sa.UUID(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valor_depreciado >= 0", name="ck_depr_mes_nao_negativo"
        ),
        sa.UniqueConstraint("bem_id", "competencia", name="uq_depr_bem_competencia"),
    )
    op.create_index("ix_depr_tenant", "depreciacao_mensal", ["tenant_id"])
    op.create_index(
        "ix_depr_competencia", "depreciacao_mensal", ["competencia"]
    )
    op.execute("ALTER TABLE depreciacao_mensal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY depreciacao_mensal_tenant ON depreciacao_mensal USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS depreciacao_mensal_tenant ON depreciacao_mensal"
    )
    op.drop_table("depreciacao_mensal")
    op.execute(
        "DROP POLICY IF EXISTS bem_imobilizado_tenant ON bem_imobilizado"
    )
    op.drop_table("bem_imobilizado")
    op.drop_table("tabela_depreciacao_rfb")
