"""Sprint 6 PR2 — PGDAS-D transmissão + e-CAC monitor.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-16

Tabelas:
  transmissao_pgdas — append-only. Cada tentativa de transmitir um PGDAS-D
    gera uma linha. Retificação cria nova linha com `tentativa = N+1` e
    `eh_retificadora = True`. FK para `apuracao_fiscal` (já existente, Sprint 2).

  mensagem_e_cac   — caixa postal e-CAC RFB. `id_externo_serpro` é o
    identificador da mensagem na origem; UNIQUE para idempotência do sync.
    Campos de classificação (`tipo`, `prioridade`, `prazo_resposta`) ficam
    nullable porque a primeira ingestão grava antes do classificador rodar.

Princípios aplicados (§8.1, §8.2, §8.9, §8.10).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── transmissao_pgdas ────────────────────────────────────────────────────
    op.create_table(
        "transmissao_pgdas",
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
            "apuracao_id",
            sa.UUID(),
            sa.ForeignKey("apuracao_fiscal.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        # status ∈ {pendente, transmitida, erro, retificada}
        sa.Column("tentativa", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("eh_retificadora", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("protocolo", sa.String(60), nullable=True),
        sa.Column("recibo_pdf_storage_key", sa.String(500), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("serpro_chamada_id", sa.UUID(), nullable=True),
        sa.Column("payload_envio_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("resposta_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("erro_codigo", sa.String(80), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
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
            "status IN ('pendente','transmitida','erro','retificada')",
            name="ck_transmissao_pgdas_status",
        ),
        sa.UniqueConstraint(
            "empresa_id",
            "competencia",
            "tentativa",
            name="uq_transmissao_pgdas_comp_tentativa",
        ),
    )
    op.create_index("ix_transmissao_pgdas_tenant", "transmissao_pgdas", ["tenant_id"])
    op.create_index(
        "ix_transmissao_pgdas_empresa_comp", "transmissao_pgdas", ["empresa_id", "competencia"]
    )
    op.execute("ALTER TABLE transmissao_pgdas ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY transmissao_pgdas_tenant ON transmissao_pgdas USING ({_RLS_USING})"
    )

    # ── mensagem_e_cac ───────────────────────────────────────────────────────
    op.create_table(
        "mensagem_e_cac",
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
        sa.Column("id_externo_serpro", sa.String(80), nullable=False),
        sa.Column("assunto", sa.String(255), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=True),
        sa.Column("origem", sa.String(50), nullable=False, server_default="RFB"),
        sa.Column("recebida_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lida_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=True),
        # tipo ∈ {intimacao, aviso, informativa, outro}
        sa.Column("prioridade", sa.String(10), nullable=True),
        # prioridade ∈ {alta, media, baixa}
        sa.Column("prazo_resposta", sa.Date(), nullable=True),
        sa.Column("classificada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("classificador_versao", sa.String(40), nullable=True),
        sa.Column(
            "encaminhada_marketplace",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IS NULL OR tipo IN ('intimacao','aviso','informativa','outro')",
            name="ck_mensagem_e_cac_tipo",
        ),
        sa.CheckConstraint(
            "prioridade IS NULL OR prioridade IN ('alta','media','baixa')",
            name="ck_mensagem_e_cac_prioridade",
        ),
        sa.UniqueConstraint(
            "empresa_id",
            "id_externo_serpro",
            name="uq_mensagem_e_cac_idempotente",
        ),
    )
    op.create_index("ix_mensagem_e_cac_tenant", "mensagem_e_cac", ["tenant_id"])
    op.create_index(
        "ix_mensagem_e_cac_empresa_recebida", "mensagem_e_cac", ["empresa_id", "recebida_em"]
    )
    op.create_index(
        "ix_mensagem_e_cac_nao_lidas",
        "mensagem_e_cac",
        ["empresa_id"],
        postgresql_where=sa.text("lida_em IS NULL"),
    )
    op.execute("ALTER TABLE mensagem_e_cac ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY mensagem_e_cac_tenant ON mensagem_e_cac USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS mensagem_e_cac_tenant ON mensagem_e_cac")
    op.drop_table("mensagem_e_cac")
    op.execute("DROP POLICY IF EXISTS transmissao_pgdas_tenant ON transmissao_pgdas")
    op.drop_table("transmissao_pgdas")
