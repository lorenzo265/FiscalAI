"""Sprint 5 — WhatsApp + NFS-e + Onboarding.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12

Mudanças (backward-compatible — colunas novas são nullable):
  empresa.whatsapp_phone        — número WhatsApp E.164 (nullable)
  documento_fiscal.focus_ref    — ref de idempotência Focus NFe (nullable)
  sessao_whatsapp               — estado de conversa WhatsApp por tenant/phone

Princípios aplicados (§8 do Plano):
  8.1 — tenant_id NOT NULL + RLS em sessao_whatsapp
  8.2 — documento_fiscal é append-only; focus_ref é só leitura após inserção
  8.9 — focus_ref deriva de uuid5(empresa_id, numero_nota) — idempotência garantida
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── empresa.whatsapp_phone (nullable — backward-compatible) ───────────────
    op.add_column(
        "empresa",
        sa.Column("whatsapp_phone", sa.String(20), nullable=True),
    )
    op.create_index("ix_empresa_whatsapp_phone", "empresa", ["whatsapp_phone"])

    # ── documento_fiscal.focus_ref (nullable — backward-compatible) ───────────
    op.add_column(
        "documento_fiscal",
        sa.Column("focus_ref", sa.String(100), nullable=True),
    )
    op.create_index("ix_doc_focus_ref", "documento_fiscal", ["focus_ref"])

    # ── sessao_whatsapp ───────────────────────────────────────────────────────
    op.create_table(
        "sessao_whatsapp",
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
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column(
            "estado",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "mensagens_na_sessao",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_sessao_whatsapp_tenant_phone"),
    )
    op.create_index("ix_sessao_whatsapp_phone", "sessao_whatsapp", ["phone"])
    op.create_index("ix_sessao_whatsapp_tenant", "sessao_whatsapp", ["tenant_id"])

    # RLS: cada tenant vê apenas suas próprias sessões
    op.execute("ALTER TABLE sessao_whatsapp ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY sessao_whatsapp_tenant ON sessao_whatsapp "
        f"USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS sessao_whatsapp_tenant ON sessao_whatsapp")
    op.drop_table("sessao_whatsapp")
    op.drop_index("ix_doc_focus_ref", table_name="documento_fiscal")
    op.drop_column("documento_fiscal", "focus_ref")
    op.drop_index("ix_empresa_whatsapp_phone", table_name="empresa")
    op.drop_column("empresa", "whatsapp_phone")
