"""Sprint 7 PR2 — transações bancárias + dedup de eventos webhook.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-17

Tabelas:
  transacao_bancaria      — UPSERT idempotente por `pluggy_transaction_id`.
                            `valor` é signed: positivo = entrada (CREDIT),
                            negativo = saída (DEBIT). `raw_json` guarda o
                            snapshot bruto Pluggy para auditoria.

  pluggy_webhook_event    — dedup de webhooks por `pluggy_event_id`. Eventos
                            duplicados retornam HTTP 200 sem processar (idem-
                            potência §8.9).

Princípios aplicados (§8.1, §8.2, §8.9).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── transacao_bancaria ───────────────────────────────────────────────────
    op.create_table(
        "transacao_bancaria",
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
            "conta_bancaria_id",
            sa.UUID(),
            sa.ForeignKey("conta_bancaria.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pluggy_transaction_id", sa.String(80), nullable=False),
        sa.Column("data_transacao", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(18, 2), nullable=False),
        # valor signed: > 0 entrada, < 0 saída
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        # tipo ∈ {CREDIT, DEBIT}
        sa.Column("status", sa.String(20), nullable=False, server_default="CONFIRMED"),
        # status ∈ {PENDING, CONFIRMED}
        sa.Column("categoria_pluggy", sa.String(80), nullable=True),
        sa.Column("merchant_cnpj", sa.String(14), nullable=True),
        sa.Column("merchant_nome", sa.String(255), nullable=True),
        sa.Column("raw_json", sa.dialects.postgresql.JSONB(), nullable=False),
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
        sa.CheckConstraint("tipo IN ('CREDIT','DEBIT')", name="ck_transacao_tipo"),
        sa.CheckConstraint(
            "status IN ('PENDING','CONFIRMED')", name="ck_transacao_status"
        ),
        sa.UniqueConstraint(
            "pluggy_transaction_id", name="uq_transacao_pluggy_id"
        ),
    )
    op.create_index("ix_transacao_tenant", "transacao_bancaria", ["tenant_id"])
    op.create_index(
        "ix_transacao_conta_data",
        "transacao_bancaria",
        ["conta_bancaria_id", "data_transacao"],
    )
    op.create_index(
        "ix_transacao_empresa_data",
        "transacao_bancaria",
        ["empresa_id", "data_transacao"],
    )
    op.execute("ALTER TABLE transacao_bancaria ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY transacao_bancaria_tenant ON transacao_bancaria USING ({_RLS_USING})"
    )

    # ── pluggy_webhook_event (dedup) ─────────────────────────────────────────
    op.create_table(
        "pluggy_webhook_event",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pluggy_event_id", sa.String(80), nullable=False),
        sa.Column("pluggy_item_id", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        # event_type ∈ {item/updated, item/created, item/login_succeeded,
        #               item/error, transactions/created, transactions/updated, ...}
        sa.Column("payload_json", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "processado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "recebido_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "pluggy_event_id", name="uq_pluggy_webhook_event_id"
        ),
    )
    op.create_index(
        "ix_pluggy_webhook_item", "pluggy_webhook_event", ["pluggy_item_id"]
    )
    # Tabela é cross-tenant (não tem tenant_id) — webhook chega antes do
    # routing por item_id. Acesso restrito ao endpoint do webhook.


def downgrade() -> None:
    op.drop_table("pluggy_webhook_event")
    op.execute(
        "DROP POLICY IF EXISTS transacao_bancaria_tenant ON transacao_bancaria"
    )
    op.drop_table("transacao_bancaria")
