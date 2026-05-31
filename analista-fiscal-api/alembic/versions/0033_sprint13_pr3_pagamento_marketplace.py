"""Sprint 13 PR3 — Pagamento stub do marketplace + GRANT/REVOKE complementares.

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-21

Tabela ``cobranca_consulta``:

  * 1 cobrança por consulta (UNIQUE em ``consulta_id``).
  * ``idempotency_key`` UNIQUE — webhook do provider pode chegar 2× sob
    retry; INSERT/UPDATE idempotentes garantem ausência de double-spend
    (§8.9).
  * RLS por tenant (cliente PME vê suas cobranças) + GRANT SELECT para a
    role ``marketplace_partner`` (parceiro consulta status do que ganhou).
  * REVOKE UPDATE/DELETE FROM PUBLIC — `status` muda só via webhook
    autenticado; cobranças nunca somem (audit + LGPD).

Pagamento real (Stripe Connect / Pagar.me / Pix Cobrança v2) fica
documentado em ``docs/adr/0015-marketplace-pagamento-provider-stub.md`` e
``docs/pendencias/marketplace-pagamento-real.md`` — esta migration encaixa o
schema mas o ``_FakeProvider`` é quem responde no MVP.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "cobranca_consulta",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "consulta_id", sa.UUID(),
            sa.ForeignKey("consulta_marketplace.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False, server_default="fake"),
        sa.Column("provider_externo_id", sa.String(120), nullable=True),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pendente",
        ),
        sa.Column("checkout_url", sa.String(2048), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("paga_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pendente','paga','falhou','cancelada')",
            name="ck_cobranca_status",
        ),
        sa.CheckConstraint(
            "valor >= 0",
            name="ck_cobranca_valor",
        ),
        sa.UniqueConstraint("consulta_id", name="uq_cobranca_consulta"),
        sa.UniqueConstraint("idempotency_key", name="uq_cobranca_idempotency"),
    )
    op.create_index(
        "ix_cobranca_tenant", "cobranca_consulta", ["tenant_id"],
    )
    op.create_index(
        "ix_cobranca_status", "cobranca_consulta", ["status"],
    )

    op.execute("ALTER TABLE cobranca_consulta ENABLE ROW LEVEL SECURITY")
    # Sem FORCE — webhook do provider precisa de bypass para atualizar status
    # sem conhecer o tenant. Conexão de webhook usa role superuser (fiscal);
    # endpoints autenticados de cliente passam por SET LOCAL ROLE fiscal_app
    # + app.tenant_id e respeitam a policy abaixo.
    op.execute(
        f"CREATE POLICY cobranca_tenant ON cobranca_consulta "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    op.execute(
        "GRANT SELECT ON cobranca_consulta TO marketplace_partner"
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON cobranca_consulta FROM PUBLIC"
    )

    # Webhook do provider precisa atualizar status sem RLS (rota de sistema,
    # mesmo pattern do whatsapp_mensagem_processada). Service usa
    # ``SET LOCAL ROLE postgres`` ou conexão direta — não cobramos via policy.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS cobranca_tenant ON cobranca_consulta")
    op.drop_table("cobranca_consulta")
