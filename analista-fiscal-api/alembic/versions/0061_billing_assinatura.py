"""Billing — assinatura, fatura, evento_billing (Marco 2 produção).

Revision ID: 0061
Revises: 0060
Create Date: 2026-06-21

Cria as 3 tabelas do bounded context de billing (assinatura SaaS do cliente
ao Arkan via Stripe), todas com RLS multi-tenant (USING + WITH CHECK).

  * ``assinatura`` — uma viva por tenant; status trial/ativa/inadimplente/cancelada.
  * ``fatura`` — espelho das invoices do Stripe.
  * ``evento_billing`` — idempotência do webhook (stripe_event_id UNIQUE);
    ``tenant_id`` nullable (eventos globais). A policy via NULLIF trata NULL.

ENABLE (NÃO FORCE) ROW LEVEL SECURITY: o webhook do Stripe escreve via
``get_webhook_session`` (sessão superuser, sem SET ROLE) que bypassa o RLS —
mesmo padrão do ``cobranca_consulta`` do marketplace. Os endpoints autenticados
usam ``get_session`` (SET ROLE fiscal_app + app.tenant_id) e respeitam a policy.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "assinatura",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("plano_codigo", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("checkout_url", sa.String(1000), nullable=True),
        sa.Column("planos_versao", sa.String(40), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "atualizado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('trial','ativa','inadimplente','cancelada')",
            name="ck_assinatura_status",
        ),
    )
    op.create_index("ix_assinatura_tenant", "assinatura", ["tenant_id"])
    op.create_index(
        "ix_assinatura_stripe_sub", "assinatura", ["stripe_subscription_id"]
    )
    op.execute("ALTER TABLE assinatura ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY assinatura_tenant ON assinatura "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )

    op.create_table(
        "fatura",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "assinatura_id", sa.UUID(),
            sa.ForeignKey("assinatura.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("valor", sa.NUMERIC(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="aberta"),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=True),
        sa.Column("competencia", sa.DATE(), nullable=False),
        sa.Column("pago_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('aberta','paga','falhou','cancelada')",
            name="ck_fatura_status",
        ),
        sa.UniqueConstraint("stripe_invoice_id", name="uq_fatura_stripe_invoice"),
    )
    op.create_index("ix_fatura_tenant", "fatura", ["tenant_id"])
    op.create_index("ix_fatura_assinatura", "fatura", ["assinatura_id"])
    op.execute("ALTER TABLE fatura ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY fatura_tenant ON fatura "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )

    op.create_table(
        "evento_billing",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(80), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "processado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint(
            "stripe_event_id", name="uq_evento_billing_stripe_event"
        ),
    )
    op.create_index(
        "ix_evento_billing_stripe", "evento_billing", ["stripe_event_id"]
    )
    op.execute("ALTER TABLE evento_billing ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY evento_billing_tenant ON evento_billing "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )

    # GRANT explícito ao role das sessões autenticadas (SET LOCAL ROLE
    # fiscal_app). Não confiamos no ALTER DEFAULT PRIVILEGES do init.sql —
    # inconsistente para tabelas criadas via alembic. O webhook do Stripe usa
    # o role superuser ``fiscal`` (bypassa RLS), então não precisa de GRANT.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON assinatura, fatura, evento_billing TO fiscal_app"
    )


def downgrade() -> None:
    op.drop_table("evento_billing")
    op.drop_table("fatura")
    op.drop_table("assinatura")
