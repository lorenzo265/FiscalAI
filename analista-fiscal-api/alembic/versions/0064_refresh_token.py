"""Refresh token DB-backed com rotacao + revogacao (Marco 3).

Revision ID: 0064
Revises: 0063
Create Date: 2026-06-22

Cria ``refresh_token`` -- guarda o SHA-256 hex do token (nunca o valor cru),
encadeado por ``family_id`` para rotacao e deteccao de reuso. RLS multi-tenant.

ENABLE (NAO FORCE) ROW LEVEL SECURITY: a EMISSAO (login/register) roda sob
``get_session``/anon com ``app.tenant_id`` setado (RLS WITH CHECK ok). A
RENOVACAO (POST /auth/refresh) e PRE-autenticacao -- busca por hash global unico
sob ``get_system_session`` (superuser, bypassa RLS). O GRANT a fiscal_app cobre
a emissao + a revogacao na exclusao LGPD (ambas tenant-scoped).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "refresh_token",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )
    op.create_index("ix_refresh_token_family", "refresh_token", ["family_id"])
    op.create_index("ix_refresh_token_tenant", "refresh_token", ["tenant_id"])
    op.execute("ALTER TABLE refresh_token ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY refresh_token_tenant ON refresh_token "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_token TO fiscal_app"
    )


def downgrade() -> None:
    op.drop_table("refresh_token")
