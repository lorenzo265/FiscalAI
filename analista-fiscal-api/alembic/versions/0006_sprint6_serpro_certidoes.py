"""Sprint 6 — SERPRO Integra Contador + certidões (CND/CRF/CNDT).

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-16

Princípios aplicados (§8 do Plano):
  8.1  — tenant_id NOT NULL + RLS em todas as tabelas novas
  8.2  — `certidao` é append-only; renovação cria nova linha, antigas ficam com
         valid_until passado
  8.7  — campo do certificado p12 do cliente é criptografado via pgcrypto (PGP
         symmetric) com chave envelopada por KMS (SERPRO_CERT_ENCRYPTION_KEY)
  8.10 — `serpro_chamada` mantém audit log de cada chamada SERPRO para tracing
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── serpro_credencial ────────────────────────────────────────────────────
    # Armazena cert e-CNPJ do cliente (.p12) e senha, criptografados via
    # pgcrypto. Uma linha por empresa.
    op.create_table(
        "serpro_credencial",
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
        sa.Column("cert_p12_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("cert_senha_cifrada", sa.LargeBinary(), nullable=False),
        sa.Column("cert_valid_until", sa.Date(), nullable=False),
        sa.Column("termo_delegacao_assinado_em", sa.TIMESTAMP(timezone=True), nullable=False),
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
        sa.UniqueConstraint("empresa_id", name="uq_serpro_credencial_empresa"),
    )
    op.create_index("ix_serpro_credencial_tenant", "serpro_credencial", ["tenant_id"])
    op.execute("ALTER TABLE serpro_credencial ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY serpro_credencial_tenant ON serpro_credencial USING ({_RLS_USING})"
    )

    # ── certidao ─────────────────────────────────────────────────────────────
    # Append-only. Renovação anual gera nova linha. Tipos: CND (federal),
    # CRF (FGTS / Caixa), CNDT (trabalhista / TST).
    op.create_table(
        "certidao",
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
        sa.Column("tipo", sa.String(10), nullable=False),  # CND | CRF | CNDT
        sa.Column("numero", sa.String(50), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        # status ∈ {emitida, negativa, positiva, positiva_com_efeitos_de_negativa, erro}
        sa.Column("emitida_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("pdf_storage_key", sa.String(500), nullable=True),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("serpro_chamada_id", sa.UUID(), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('CND','CRF','CNDT')",
            name="ck_certidao_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('emitida','negativa','positiva',"
            "'positiva_com_efeitos_de_negativa','erro','processando')",
            name="ck_certidao_status",
        ),
    )
    op.create_index("ix_certidao_tenant", "certidao", ["tenant_id"])
    op.create_index("ix_certidao_empresa_tipo", "certidao", ["empresa_id", "tipo"])
    op.create_index("ix_certidao_valid_until", "certidao", ["valid_until"])
    op.execute("ALTER TABLE certidao ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY certidao_tenant ON certidao USING ({_RLS_USING})")

    # ── serpro_chamada (audit log) ───────────────────────────────────────────
    op.create_table(
        "serpro_chamada",
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
        sa.Column("servico", sa.String(60), nullable=False),
        # servico ∈ {certidao_cnd, certidao_crf, certidao_cndt, pgdas_d,
        #            dctfweb, ecac_caixa, ecac_intimacoes, das_emissao, ...}
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status_http", sa.Integer(), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("erro_codigo", sa.String(80), nullable=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "empresa_id",
            "servico",
            "idempotency_key",
            name="uq_serpro_chamada_idempotente",
        ),
    )
    op.create_index("ix_serpro_chamada_tenant", "serpro_chamada", ["tenant_id"])
    op.create_index("ix_serpro_chamada_servico_data", "serpro_chamada", ["servico", "criado_em"])
    op.execute("ALTER TABLE serpro_chamada ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY serpro_chamada_tenant ON serpro_chamada USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS serpro_chamada_tenant ON serpro_chamada")
    op.drop_table("serpro_chamada")
    op.execute("DROP POLICY IF EXISTS certidao_tenant ON certidao")
    op.drop_table("certidao")
    op.execute("DROP POLICY IF EXISTS serpro_credencial_tenant ON serpro_credencial")
    op.drop_table("serpro_credencial")
