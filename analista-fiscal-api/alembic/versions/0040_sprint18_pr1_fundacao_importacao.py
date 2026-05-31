"""Sprint 18 PR1 — Fundação da migração de escritório antigo.

Revision ID: 0040
Revises: 0039
Create Date: 2026-05-25

Três entregas, todas pré-condição do importador SPED histórico (PR2+):

1. ``documento_fiscal_item`` — granularidade por item da NF-e (pendência #26
   resolvida). Hoje ``documento_fiscal`` carrega só cabeçalho; importador
   EFD-Contribuições precisa do C170 detalhado (NCM, CFOP, CST por linha)
   para escriturar PIS/Cofins por item sem colapsar em "MERC-GENERICO".

   Constraints:
     * UNIQUE(documento_fiscal_id, n_item)        ← idempotência re-ingest
     * quantidade > 0, valor_unitario >= 0
     * cfop ~ '^\\d{4}$'                          ← formato CFOP RFB
     * cst_icms/pis/cofins formato 2-3 dígitos
     * ON DELETE CASCADE                          ← documento sumiu → itens somem

2. ``lote_importacao`` — auditoria de cada importação SPED/CSV. Estados:
   processando → concluido | falhou. ``resumo_jsonb`` carrega contagens
   (linhas processadas, lançamentos criados, documentos criados) e
   ``erros_jsonb`` carrega warnings/erros estruturados (chave NF
   duplicada, conta sem mapeamento, etc.).

   Fontes aceitas:
     - sped_ecd, sped_ecf, sped_efd_contribuicoes, sped_efd_icms_ipi
     - csv_balancete, csv_razao

3. ``lancamento_contabil.origem_tipo`` — estende CHECK para aceitar
   ``'importacao'``. DROP + ADD CONSTRAINT (Postgres não permite ALTER
   CHECK in-place). Backward-compatible: o conjunto é superset.

Princípios cravados:
  * §8.1 RLS — toda tabela nova tem ROW LEVEL SECURITY + policy.
  * §8.2 Fatos imutáveis — itens herdam o ciclo de vida do documento
    via ``superseded_by`` no pai. Não há ``superseded_by`` no item:
    quando documento é re-emitido, novo cabeçalho + novos itens.
  * §8.9 Idempotência — UNIQUE em itens + (origem_tipo, origem_id)
    já existente em lancamento_contabil cobre re-import.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── documento_fiscal_item ────────────────────────────────────────────────
    op.create_table(
        "documento_fiscal_item",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "documento_fiscal_id", sa.UUID(),
            sa.ForeignKey("documento_fiscal.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("n_item", sa.Integer(), nullable=False),
        sa.Column("codigo_produto", sa.String(60), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("ncm", sa.String(8), nullable=True),
        sa.Column("cfop", sa.String(4), nullable=True),
        sa.Column("cst_icms", sa.String(3), nullable=True),
        sa.Column("cst_pis", sa.String(2), nullable=True),
        sa.Column("cst_cofins", sa.String(2), nullable=True),
        sa.Column("unidade", sa.String(6), nullable=True),
        sa.Column("quantidade", sa.Numeric(15, 4), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(15, 4), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_icms", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_ipi", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_pis", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_cofins", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_cbs", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_ibs", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint(
            "documento_fiscal_id", "n_item",
            name="uq_doc_item_documento_n",
        ),
        sa.CheckConstraint(
            "n_item >= 1", name="ck_doc_item_n_positivo",
        ),
        sa.CheckConstraint(
            "quantidade > 0", name="ck_doc_item_qtd_positiva",
        ),
        sa.CheckConstraint(
            "valor_unitario >= 0", name="ck_doc_item_unit_nao_negativo",
        ),
        sa.CheckConstraint(
            "valor_total >= 0", name="ck_doc_item_total_nao_negativo",
        ),
        sa.CheckConstraint(
            r"cfop IS NULL OR cfop ~ '^\d{4}$'",
            name="ck_doc_item_cfop_formato",
        ),
        sa.CheckConstraint(
            r"ncm IS NULL OR ncm ~ '^\d{8}$'",
            name="ck_doc_item_ncm_formato",
        ),
        sa.CheckConstraint(
            r"cst_icms IS NULL OR cst_icms ~ '^\d{2,3}$'",
            name="ck_doc_item_cst_icms_formato",
        ),
        sa.CheckConstraint(
            r"cst_pis IS NULL OR cst_pis ~ '^\d{2}$'",
            name="ck_doc_item_cst_pis_formato",
        ),
        sa.CheckConstraint(
            r"cst_cofins IS NULL OR cst_cofins ~ '^\d{2}$'",
            name="ck_doc_item_cst_cofins_formato",
        ),
    )
    op.create_index(
        "ix_doc_item_tenant", "documento_fiscal_item", ["tenant_id"],
    )
    op.create_index(
        "ix_doc_item_documento", "documento_fiscal_item",
        ["documento_fiscal_id", "n_item"],
    )
    op.create_index(
        "ix_doc_item_ncm", "documento_fiscal_item", ["ncm"],
        postgresql_where=sa.text("ncm IS NOT NULL"),
    )
    op.execute(
        "ALTER TABLE documento_fiscal_item ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"CREATE POLICY documento_fiscal_item_tenant ON documento_fiscal_item "
        f"USING ({_RLS_USING})"
    )
    # §8.2 — item herda imutabilidade do pai.
    op.execute(
        "REVOKE UPDATE, DELETE ON documento_fiscal_item FROM PUBLIC"
    )

    # ── lote_importacao ──────────────────────────────────────────────────────
    op.create_table(
        "lote_importacao",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fonte", sa.String(40), nullable=False),
        sa.Column(
            "arquivo_sped_id", sa.UUID(),
            sa.ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nome_arquivo", sa.String(255), nullable=True),
        sa.Column("hash_arquivo", sa.String(64), nullable=True),
        sa.Column(
            "iniciado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "concluido_em", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="processando",
        ),
        sa.Column(
            "resumo_jsonb",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "erros_jsonb",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.CheckConstraint(
            "fonte IN ('sped_ecd','sped_ecf','sped_efd_contribuicoes',"
            "'sped_efd_icms_ipi','csv_balancete','csv_razao')",
            name="ck_lote_fonte",
        ),
        sa.CheckConstraint(
            "status IN ('processando','concluido','falhou')",
            name="ck_lote_status",
        ),
        sa.CheckConstraint(
            "hash_arquivo IS NULL OR hash_arquivo ~ '^[0-9a-f]{64}$'",
            name="ck_lote_hash_formato",
        ),
        sa.CheckConstraint(
            "(status = 'processando' AND concluido_em IS NULL) "
            "OR (status IN ('concluido','falhou') AND concluido_em IS NOT NULL)",
            name="ck_lote_status_concluido_coerente",
        ),
    )
    op.create_index("ix_lote_tenant", "lote_importacao", ["tenant_id"])
    op.create_index(
        "ix_lote_empresa_fonte", "lote_importacao",
        ["empresa_id", "fonte", "iniciado_em"],
    )
    # Idempotência por hash de arquivo: 1 lote concluído por (empresa, hash).
    op.create_index(
        "uq_lote_empresa_hash_concluido", "lote_importacao",
        ["empresa_id", "hash_arquivo"],
        unique=True,
        postgresql_where=sa.text(
            "hash_arquivo IS NOT NULL AND status = 'concluido'"
        ),
    )
    op.execute("ALTER TABLE lote_importacao ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY lote_importacao_tenant ON lote_importacao "
        f"USING ({_RLS_USING})"
    )

    # ── lancamento_contabil: estende CHECK origem_tipo ───────────────────────
    op.drop_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", type_="check",
    )
    op.create_check_constraint(
        "ck_lanc_origem_tipo",
        "lancamento_contabil",
        "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
        "'provisao','encerramento','ajuste','importacao')",
    )


def downgrade() -> None:
    # Reverte CHECK (sem 'importacao').
    op.drop_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", type_="check",
    )
    op.create_check_constraint(
        "ck_lanc_origem_tipo",
        "lancamento_contabil",
        "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
        "'provisao','encerramento','ajuste')",
    )

    op.execute("DROP POLICY IF EXISTS lote_importacao_tenant ON lote_importacao")
    op.drop_table("lote_importacao")

    op.execute(
        "DROP POLICY IF EXISTS documento_fiscal_item_tenant "
        "ON documento_fiscal_item"
    )
    op.drop_table("documento_fiscal_item")
