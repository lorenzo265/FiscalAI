"""Sprint 15 PR3 — Tabela ``digest_semanal`` (AI Advisor weekly digest).

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-24

Snapshot semanal proativo (segunda 06:00 BR) com 3-5 highlights da semana:
apurações fechadas, anomalias abertas, próximos vencimentos e sugestões de
otimização. Texto pronto para envio via WhatsApp utility template (envio
real fica como pendência consciente — depende de template aprovado Meta).

Append-only (§8.2): re-gerações na mesma semana criam nova linha com
``superseded_by`` apontando para a anterior. UNIQUE parcial garante uma
versão ativa por ``(empresa, semana_iso)`` (§8.9 — idempotência).

Princípios cravados (DB):

  * §8.1 — RLS multi-tenant.
  * §8.2 — snapshot imutável via supersedes.
  * §8.5 — citações persistidas em JSONB para auditoria.
  * §8.6 — ``fonte_redacao`` discrimina template determinístico × LLM × fallback.
  * §8.9 — UNIQUE parcial + ``idempotency_key`` UNIQUE.
  * §8.10 — ``custo_usd``, ``tokens_*``, ``llm_provider`` persistidos.

CHECKs:

  * ``status`` ∈ {preparado, enviado, cancelado}
  * ``fonte_redacao`` ∈ {template, llm_gemini_flash, llm_fallback}
  * ``periodo_fim >= periodo_inicio``
  * ``semana_iso ~ '^\\d{4}-W\\d{2}$'`` (ex.: "2026-W21")
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "digest_semanal",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("semana_iso", sa.String(10), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=False),
        sa.Column("periodo_fim", sa.Date(), nullable=False),
        sa.Column(
            "conteudo_estruturado", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        sa.Column("texto_redigido", sa.Text(), nullable=False),
        sa.Column("fonte_redacao", sa.String(30), nullable=False),
        sa.Column(
            "citacoes", sa.dialects.postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="preparado"),
        sa.Column("llm_provider", sa.String(40), nullable=True),
        sa.Column("custo_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("tokens_cached", sa.Integer(), nullable=True),
        sa.Column(
            "enviado_via_whatsapp_em", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column(
            "superseded_by", sa.UUID(),
            sa.ForeignKey("digest_semanal.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('preparado','enviado','cancelado')",
            name="ck_digest_status",
        ),
        sa.CheckConstraint(
            "fonte_redacao IN ('template','llm_gemini_flash','llm_fallback')",
            name="ck_digest_fonte_redacao",
        ),
        sa.CheckConstraint(
            "periodo_fim >= periodo_inicio",
            name="ck_digest_periodo_coerente",
        ),
        sa.CheckConstraint(
            "semana_iso ~ '^[0-9]{4}-W[0-9]{2}$'",
            name="ck_digest_semana_iso_formato",
        ),
        sa.CheckConstraint(
            "custo_usd IS NULL OR custo_usd >= 0",
            name="ck_digest_custo_positivo",
        ),
    )
    op.create_index("ix_digest_tenant", "digest_semanal", ["tenant_id"])
    op.create_index(
        "ix_digest_empresa_semana", "digest_semanal",
        ["empresa_id", "semana_iso"],
    )
    # UNIQUE parcial — 1 versão ativa por (empresa, semana_iso).
    op.create_index(
        "uq_digest_ativa", "digest_semanal",
        ["empresa_id", "semana_iso"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.create_index(
        "uq_digest_idempotency", "digest_semanal",
        ["idempotency_key"],
        unique=True,
    )
    op.execute("ALTER TABLE digest_semanal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY digest_semanal_tenant ON digest_semanal "
        f"USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS digest_semanal_tenant ON digest_semanal")
    op.drop_table("digest_semanal")
