"""Sprint 19.5 PR3 — Scraper DOU + LLM extrai estrutura (sugestao_vigencia_tabela).

Revision ID: 0044
Revises: 0043
Create Date: 2026-05-27

Camada 3 do painel admin. Worker mensal ``tabelas.varrer_dou_mensal`` baixa
matérias do Diário Oficial da União, extrai PDFs via ``pdfplumber``, passa
para um LLM (Gemini 2.5 Flash) com prompt versionado que devolve JSON
estruturado matching ``VigenciaInssIn`` (e similares), aplica re-check
determinístico §8.6 e **persiste como sugestão pendente** — NUNCA cria
vigência tributária diretamente. Princípio inviolável §8.8.

Tabela ``sugestao_vigencia_tabela``:

  * Cross-tenant operacional (sem RLS). Mesma família do
    ``vigencia_tabela_log`` e ``alerta_admin``.
  * Idempotência §8.9: ``idempotency_key UUID UNIQUE`` derivada de
    ``uuid5(NS_TABELA_ADMIN, "dou|{url}|{tipo_tabela}")`` — varrer 2× no
    mesmo mês não duplica sugestão.
  * Status: ``pendente`` (default — admin precisa revisar) → ``aprovada``
    (chama Camada 1 com payload, popula ``vigencia_tabela_log_id``) /
    ``rejeitada`` (admin descarta com motivo) / ``expirada`` (worker
    marca após 60 dias sem decisão).
  * Re-check §8.6: ``recheck_passou: bool`` + ``recheck_observacoes JSONB``
    — UI destaca em vermelho quando false (admin pode aprovar mesmo
    assim, com warning explícito).
  * Citação obrigatória §8.5: ``fonte_norma`` (preenchido pelo LLM citando
    matéria DOU + página) + ``fonte_dou_url`` + ``fonte_dou_pagina``.
  * LLM metadata: ``llm_modelo``/``llm_versao_prompt``/``llm_confianca``
    para auditoria + reprodutibilidade.

Princípios cravados:

  * §8.5 — fonte_norma NOT NULL + char_length ≥ 10 (mesmo CHECK do log audit).
  * §8.8 — não cria vigência; aprovação é ato consciente do admin.
  * §8.9 — idempotency_key UUID UNIQUE.
  * §8.10 — vigencia_tabela_log_id FK preserva rastreabilidade quando aprovada.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | None = None
depends_on: str | None = None


_TIPOS_SUPORTADOS: tuple[str, ...] = (
    "inss",
    "irrf",
    "fgts",
    "simples_nacional",
    "presuncao_lp",
    "icms_uf",
    "cbs_ibs",
)

_STATUS_VALIDOS: tuple[str, ...] = (
    "pendente",
    "aprovada",
    "rejeitada",
    "expirada",
)


def upgrade() -> None:
    op.create_table(
        "sugestao_vigencia_tabela",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tipo_tabela", sa.String(40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column(
            "payload_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("fonte_norma", sa.Text(), nullable=False),
        sa.Column("fonte_dou_url", sa.Text(), nullable=True),
        sa.Column("fonte_dou_pagina", sa.Integer(), nullable=True),
        sa.Column("llm_modelo", sa.String(50), nullable=False),
        sa.Column("llm_versao_prompt", sa.String(50), nullable=False),
        sa.Column(
            "llm_confianca", sa.Numeric(3, 2), nullable=False
        ),  # 0.00 .. 1.00
        sa.Column("recheck_passou", sa.Boolean(), nullable=False),
        sa.Column(
            "recheck_observacoes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pendente'"),
        ),
        sa.Column(
            "aprovada_em",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "aprovada_por_usuario_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "rejeitada_motivo", sa.Text(), nullable=True
        ),
        sa.Column(
            "vigencia_tabela_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "vigencia_tabela_log.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "idempotency_key",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_tabela IN ("
            + ",".join(f"'{t}'" for t in _TIPOS_SUPORTADOS)
            + ")",
            name="ck_sugestao_tipo",
        ),
        sa.CheckConstraint(
            "status IN ("
            + ",".join(f"'{s}'" for s in _STATUS_VALIDOS)
            + ")",
            name="ck_sugestao_status",
        ),
        sa.CheckConstraint(
            "char_length(fonte_norma) >= 10",
            name="ck_sugestao_fonte_minima",
        ),
        sa.CheckConstraint(
            "llm_confianca >= 0 AND llm_confianca <= 1",
            name="ck_sugestao_confianca_intervalo",
        ),
        sa.CheckConstraint(
            "(status = 'aprovada') = (aprovada_em IS NOT NULL)",
            name="ck_sugestao_aprovada_coerente",
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_sugestao_idempotency"
        ),
    )

    # Index parcial para o filtro padrão da UI (status='pendente').
    op.execute(
        "CREATE INDEX ix_sugestao_pendentes "
        "ON sugestao_vigencia_tabela (tipo_tabela, criado_em DESC) "
        "WHERE status = 'pendente'"
    )
    op.create_index(
        "ix_sugestao_status",
        "sugestao_vigencia_tabela",
        ["status", sa.text("criado_em DESC")],
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON sugestao_vigencia_tabela "
        "TO tax_table_admin"
    )
    op.execute("REVOKE DELETE ON sugestao_vigencia_tabela FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT DELETE ON sugestao_vigencia_tabela TO PUBLIC")
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE ON sugestao_vigencia_tabela "
        "FROM tax_table_admin"
    )
    op.drop_index("ix_sugestao_status", table_name="sugestao_vigencia_tabela")
    op.execute("DROP INDEX IF EXISTS ix_sugestao_pendentes")
    op.drop_table("sugestao_vigencia_tabela")
