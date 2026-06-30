"""NF-e Destinada + Cursor de DistribuiçãoDFe — MD-e PR2.

Revision ID: 0068
Revises: 0067
Create Date: 2026-06-29

Tabela ``nfe_destinada``:
  * Armazena cada NF-e descoberta pelo DistribuiçãoDFe (resNFe ou nfeProc).
  * UNIQUE (empresa_id, chave_nfe) — a mesma chave pode chegar como resumo
    (resNFe) e depois como XML completo (nfeProc após Ciência); o upsert
    actualiza em vez de duplicar (§8.9).
  * RLS multi-tenant (§8.1) — padrão vigente: USING + WITH CHECK + GRANT.

Tabela ``nfe_distribuicao_cursor``:
  * Uma linha por empresa — controla o NSU máximo já consumido.
  * PK = empresa_id (um único cursor por empresa).
  * Atualizada atomicamente com cada batch de sincronização.
  * RLS multi-tenant idêntico.

Fonte normativa: NT 2014.002 v1.20 / Leiaute DistribuiçãoDFe (retDistDFeInt).
  * ``ultNSU`` — último NSU processado na consulta (avança a cada batch).
  * ``maxNSU`` — maior NSU existente no AN para o CNPJ/CPF consultado.
  * Quando ``ultNSU == maxNSU``, não há mais documentos a consumir.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── tabela nfe_destinada ─────────────────────────────────────────────────
    op.create_table(
        "nfe_destinada",
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
        # Chave de acesso NF-e — 44 dígitos numéricos (NT 2014.002)
        sa.Column("chave_nfe", sa.String(44), nullable=False),
        # NSU do documento neste CNPJ (cresce monotonicamente)
        sa.Column("nsu", sa.BigInteger(), nullable=False),
        # Dados do emitente (do resNFe / nfeProc)
        sa.Column("emitente_cnpj", sa.String(14), nullable=True),
        sa.Column("emitente_nome", sa.String(120), nullable=True),
        # Valor total da NF-e (NUMERIC, nunca float)
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=True),
        # Data/hora de emissão da NF-e
        sa.Column("dh_emissao", sa.TIMESTAMP(timezone=True), nullable=True),
        # Tipo de documento distribuído: 'resumo' (resNFe) ou 'completo' (nfeProc)
        sa.Column(
            "tipo_documento",
            sa.String(10),
            nullable=False,
            server_default="resumo",
        ),
        # True quando o XML completo já foi recebido (após Ciência registrada)
        sa.Column(
            "tem_xml_completo", sa.Boolean(), nullable=False, server_default="false"
        ),
        # Chave do XML completo no object storage (preenchida em PR3)
        sa.Column("xml_storage_key", sa.Text(), nullable=True),
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
        # CHECKs
        sa.CheckConstraint(
            r"chave_nfe ~ '^\d{44}$'",
            name="ck_nfe_destinada_chave_formato",
        ),
        sa.CheckConstraint(
            "tipo_documento IN ('resumo','completo')",
            name="ck_nfe_destinada_tipo_doc",
        ),
    )

    # Índices nfe_destinada
    op.create_index("ix_nfe_destinada_tenant", "nfe_destinada", ["tenant_id"])
    op.create_index(
        "ix_nfe_destinada_empresa_nsu", "nfe_destinada", ["empresa_id", "nsu"]
    )
    # UNIQUE operacional: uma linha por (empresa, chave) — upsert idempotente
    op.create_index(
        "uq_nfe_destinada_empresa_chave",
        "nfe_destinada",
        ["empresa_id", "chave_nfe"],
        unique=True,
    )

    # RLS (padrão vigente: billing 0061, lgpd 0062, refresh 0064, manifestacao 0067)
    op.execute("ALTER TABLE nfe_destinada ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY nfe_destinada_tenant ON nfe_destinada "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON nfe_destinada TO fiscal_app"
    )

    # ── tabela nfe_distribuicao_cursor ───────────────────────────────────────
    op.create_table(
        "nfe_distribuicao_cursor",
        # PK = empresa_id (exatamente um cursor por empresa)
        sa.Column(
            "empresa_id",
            sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # Último NSU consumido na consulta anterior (retDistDFeInt.ultNSU)
        sa.Column("ult_nsu", sa.BigInteger(), nullable=False, server_default="0"),
        # Maior NSU disponível no AN para este CNPJ (retDistDFeInt.maxNSU)
        sa.Column("max_nsu", sa.BigInteger(), nullable=False, server_default="0"),
        # Timestamp da última sincronização bem-sucedida
        sa.Column("ultima_sync_em", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_nfe_distribuicao_cursor_tenant",
        "nfe_distribuicao_cursor",
        ["tenant_id"],
    )

    # RLS
    op.execute(
        "ALTER TABLE nfe_distribuicao_cursor ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"CREATE POLICY nfe_distribuicao_cursor_tenant ON nfe_distribuicao_cursor "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON nfe_distribuicao_cursor TO fiscal_app"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS nfe_distribuicao_cursor_tenant "
        "ON nfe_distribuicao_cursor"
    )
    op.drop_table("nfe_distribuicao_cursor")

    op.execute(
        "DROP POLICY IF EXISTS nfe_destinada_tenant ON nfe_destinada"
    )
    op.drop_table("nfe_destinada")
