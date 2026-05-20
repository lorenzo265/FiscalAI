"""Sprint 1 — Fundação multi-tenant: tenant, usuario, empresa + RLS

Revision ID: 0001
Revises:
Create Date: 2026-05-10

Princípios aplicados (§8 do Plano):
  8.1 — tenant_id NOT NULL em todas as tabelas de domínio
  8.1 — RLS ativo via NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid
  8.2 — Fatos imutáveis: sem UPDATE/DELETE em audit_log (futuro §5.5)
  8.3 — updated_at em empresa para rastrear mudanças de perfil
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

# Política RLS reutilizada nas tabelas de domínio
_RLS_USING = (
    "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"
)


def upgrade() -> None:
    # ── tenant ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_tenant_slug", "tenant", ["slug"])

    # ── usuario ──────────────────────────────────────────────────────────────
    op.create_table(
        "usuario",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_usuario_tenant_email", "usuario", ["tenant_id", "email"])
    op.create_index("ix_usuario_tenant_email", "usuario", ["tenant_id", "email"])

    # RLS: tenant A não vê usuários de tenant B
    # FORCE garante que mesmo o superuser (fiscal) respeita a policy
    op.execute("ALTER TABLE usuario ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usuario FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON usuario"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )

    # ── empresa ──────────────────────────────────────────────────────────────
    op.create_table(
        "empresa",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("razao_social", sa.String(255), nullable=False),
        sa.Column("nome_fantasia", sa.String(255), nullable=True),
        sa.Column("regime_tributario", sa.String(50), nullable=False),
        sa.Column("perfil_ui", sa.String(50), nullable=False),
        sa.Column("anexo_simples", sa.CHAR(1), nullable=True),
        sa.Column("cnae_principal", sa.String(10), nullable=True),
        sa.Column("municipio", sa.String(100), nullable=True),
        sa.Column("uf", sa.CHAR(2), nullable=True),
        sa.Column("ie", sa.String(20), nullable=True),
        sa.Column("im", sa.String(20), nullable=True),
        sa.Column("faturamento_12m", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("ativa", sa.Boolean(), server_default="true", nullable=False),
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
    )
    op.create_check_constraint(
        "ck_empresa_regime",
        "empresa",
        "regime_tributario IN ('mei','simples_nacional','lucro_presumido','lucro_real')",
    )
    op.create_check_constraint(
        "ck_empresa_perfil",
        "empresa",
        "perfil_ui IN ('mei','sn_sem_funcionarios','sn_com_funcionarios','lucro_presumido','lucro_real')",
    )
    op.create_check_constraint(
        "ck_empresa_anexo",
        "empresa",
        "anexo_simples IS NULL OR anexo_simples IN ('I','II','III','IV','V')",
    )
    op.create_unique_constraint("uq_empresa_tenant_cnpj", "empresa", ["tenant_id", "cnpj"])
    op.create_index("ix_empresa_tenant", "empresa", ["tenant_id"])
    op.create_index("ix_empresa_cnpj", "empresa", ["cnpj"])
    op.create_index("ix_empresa_tenant_perfil", "empresa", ["tenant_id", "perfil_ui"])

    # FORCE garante que mesmo o superuser (fiscal) respeita a policy
    op.execute("ALTER TABLE empresa ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE empresa FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON empresa"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )


def downgrade() -> None:
    op.drop_table("empresa")
    op.drop_table("usuario")
    op.drop_table("tenant")
