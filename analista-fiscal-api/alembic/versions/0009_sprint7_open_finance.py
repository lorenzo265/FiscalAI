"""Sprint 7 PR1 — Open Finance via Pluggy: items + contas bancárias.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-17

Tabelas:
  pluggy_item     — conexão Open Finance autorizada pelo cliente via widget
                    Pluggy. Uma empresa pode ter múltiplos itens (um por
                    banco/conector). UNIQUE em `pluggy_item_id`.

  conta_bancaria  — conta extraída via Pluggy /accounts (uma ou mais por
                    item, conforme retorno). `saldo_atual` é snapshot do
                    último sync — fonte de verdade fica no banco real.

Princípios aplicados (§8.1, §8.7, §8.11):
  * RLS ativo em ambas — clientes só veem suas próprias conexões e contas.
  * NÃO armazenamos access_token ou credenciais do cliente — Pluggy gerencia
    o token, nós guardamos só o `pluggy_item_id` (insuficiente sozinho para
    consumir API; precisa da nossa API key Pluggy).
  * Consent type READ-ONLY no MVP — Pluggy é ITP autorizada, mas o produto
    não iniciará pagamentos (Pix/TED) por enquanto.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── pluggy_item ──────────────────────────────────────────────────────────
    op.create_table(
        "pluggy_item",
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
        sa.Column("pluggy_item_id", sa.String(80), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=True),
        sa.Column("connector_nome", sa.String(120), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        # status ∈ {CREATING, UPDATING, LOGIN_SUCCEEDED, LOGIN_ERROR,
        #           WAITING_USER_INPUT, OUTDATED, DELETED}
        sa.Column("status_detalhe", sa.Text(), nullable=True),
        sa.Column("erro_codigo", sa.String(80), nullable=True),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "consent_type",
            sa.String(20),
            nullable=False,
            server_default="READ_ONLY",
        ),
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
            "consent_type IN ('READ_ONLY','PAYMENT_INITIATION')",
            name="ck_pluggy_item_consent",
        ),
        sa.UniqueConstraint("pluggy_item_id", name="uq_pluggy_item_external_id"),
    )
    op.create_index("ix_pluggy_item_tenant", "pluggy_item", ["tenant_id"])
    op.create_index("ix_pluggy_item_empresa", "pluggy_item", ["empresa_id"])
    op.execute("ALTER TABLE pluggy_item ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY pluggy_item_tenant ON pluggy_item USING ({_RLS_USING})")

    # ── conta_bancaria ───────────────────────────────────────────────────────
    op.create_table(
        "conta_bancaria",
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
            "pluggy_item_id",
            sa.UUID(),
            sa.ForeignKey("pluggy_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pluggy_account_id", sa.String(80), nullable=False),
        sa.Column("banco_nome", sa.String(120), nullable=True),
        sa.Column("agencia", sa.String(20), nullable=True),
        sa.Column("numero", sa.String(30), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        # tipo ∈ {CHECKING, SAVINGS, CREDIT_CARD}
        sa.Column("subtipo", sa.String(20), nullable=True),
        sa.Column("moeda", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("saldo_atual", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("saldo_disponivel", sa.Numeric(18, 2), nullable=True),
        sa.Column("saldo_atualizado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "ativa",
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
            "tipo IN ('CHECKING','SAVINGS','CREDIT_CARD')",
            name="ck_conta_bancaria_tipo",
        ),
        sa.UniqueConstraint(
            "pluggy_account_id", name="uq_conta_bancaria_pluggy_account"
        ),
    )
    op.create_index("ix_conta_bancaria_tenant", "conta_bancaria", ["tenant_id"])
    op.create_index(
        "ix_conta_bancaria_empresa_ativa",
        "conta_bancaria",
        ["empresa_id"],
        postgresql_where=sa.text("ativa IS TRUE"),
    )
    op.execute("ALTER TABLE conta_bancaria ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY conta_bancaria_tenant ON conta_bancaria USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS conta_bancaria_tenant ON conta_bancaria")
    op.drop_table("conta_bancaria")
    op.execute("DROP POLICY IF EXISTS pluggy_item_tenant ON pluggy_item")
    op.drop_table("pluggy_item")
