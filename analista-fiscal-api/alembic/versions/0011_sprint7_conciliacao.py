"""Sprint 7 PR3 — conciliação banco × NF.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-17

Tabela ``conciliacao_match``:
  * Liga ``transacao_bancaria`` a ``documento_fiscal`` (NF-e/NFS-e).
  * ``confianca`` 0-100 calculada pelo algoritmo determinístico (§8.8 — LLM
    nunca escreve fatos; aqui é só regras puras).
  * ``tipo`` distingue automação:
      AUTO        — score ≥ 80, conciliação aplicada sem revisão
      SUGERIDA    — 50-79, requer confirmação do usuário
      MANUAL      — criada diretamente pelo usuário (sem score)
      REJEITADA   — usuário recusou a sugestão (não some — fica como negativo
                    para alimentar futuro reforço do algoritmo)
  * ``score_breakdown_json`` é audit trail dos critérios que pontuaram
    (qual valor, qual data delta, qual CNPJ etc.).

UNIQUE (transacao_id, documento_fiscal_id) — impede duplicar matches; se a
re-execução do algoritmo gerar a mesma sugestão para o mesmo par, faz no-op.

Princípios aplicados (§8.1, §8.2, §8.8, §8.10).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "conciliacao_match",
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
            "transacao_id",
            sa.UUID(),
            sa.ForeignKey("transacao_bancaria.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "documento_fiscal_id",
            sa.UUID(),
            sa.ForeignKey("documento_fiscal.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("confianca", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("algoritmo_versao", sa.String(20), nullable=False),
        sa.Column("score_breakdown_json", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "confirmado_por_usuario_id",
            sa.UUID(),
            sa.ForeignKey("usuario.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejeitado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "rejeitado_por_usuario_id",
            sa.UUID(),
            sa.ForeignKey("usuario.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "confianca BETWEEN 0 AND 100", name="ck_match_confianca"
        ),
        sa.CheckConstraint(
            "tipo IN ('AUTO','SUGERIDA','MANUAL','REJEITADA')",
            name="ck_match_tipo",
        ),
        sa.UniqueConstraint(
            "transacao_id", "documento_fiscal_id", name="uq_match_par"
        ),
    )
    op.create_index("ix_match_tenant", "conciliacao_match", ["tenant_id"])
    op.create_index(
        "ix_match_empresa_tipo", "conciliacao_match", ["empresa_id", "tipo"]
    )
    op.create_index("ix_match_transacao", "conciliacao_match", ["transacao_id"])
    op.create_index(
        "ix_match_documento", "conciliacao_match", ["documento_fiscal_id"]
    )
    op.execute("ALTER TABLE conciliacao_match ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY conciliacao_match_tenant ON conciliacao_match USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS conciliacao_match_tenant ON conciliacao_match"
    )
    op.drop_table("conciliacao_match")
