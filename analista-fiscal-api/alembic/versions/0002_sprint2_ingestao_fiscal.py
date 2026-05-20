"""Sprint 2 — Ingestão XML + DAS: documento_fiscal, tabela_simples_faixa, apuracao_fiscal.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-11

Princípios aplicados (§8 do Plano):
  8.1 — tenant_id NOT NULL em documento_fiscal e apuracao_fiscal
  8.1 — RLS policy em documento_fiscal e apuracao_fiscal
  8.2 — documento_fiscal imutável: cancelamento = nova linha com supersedes
  8.3 — tabela_simples_faixa SCD Type 2: valid_from/valid_to, nunca UPDATE
  8.4 — seed com tabelas CGSN 140/2018 + golden tests validam o algoritmo
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    # ── documento_fiscal ─────────────────────────────────────────────────────
    op.create_table(
        "documento_fiscal",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("empresa_id", sa.UUID(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("direcao", sa.String(10), nullable=False),
        sa.Column("chave", sa.String(44), nullable=True),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("serie", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="autorizada"),
        sa.Column("emitida_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("cnpj_emitente", sa.String(14), nullable=False),
        sa.Column("cnpj_destinatario", sa.String(14), nullable=True),
        sa.Column("valor_total", sa.NUMERIC(14, 2), nullable=False),
        sa.Column("valor_impostos", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_icms", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_ipi", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_pis", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_cofins", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_iss", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("cfop", sa.String(4), nullable=True),
        sa.Column("cst", sa.String(3), nullable=True),
        sa.Column("ncm", sa.String(8), nullable=True),
        sa.Column("valor_cbs", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("valor_ibs", sa.NUMERIC(14, 2), nullable=True),
        sa.Column("xml_storage_key", sa.String(500), nullable=True),
        sa.Column("pdf_storage_key", sa.String(500), nullable=True),
        sa.Column("natureza_operacao", sa.String(255), nullable=True),
        sa.Column("regime_emitente", sa.String(50), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "supersedes",
            sa.UUID(),
            sa.ForeignKey("documento_fiscal.id"),
            nullable=True,
        ),
        sa.Column("evento", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ingested_via", sa.String(50), nullable=True),
    )
    op.create_check_constraint(
        "ck_doc_tipo",
        "documento_fiscal",
        "tipo IN ('nfe','nfse','nfce','cte','mdfe','nfcom','dce')",
    )
    op.create_check_constraint(
        "ck_doc_direcao",
        "documento_fiscal",
        "direcao IN ('saida','entrada')",
    )
    op.create_index("ix_doc_chave", "documento_fiscal", ["chave"])
    op.create_index("ix_doc_empresa_tipo", "documento_fiscal", ["empresa_id", "tipo", "direcao"])
    op.create_index("ix_doc_emitida", "documento_fiscal", ["empresa_id", "emitida_em"])
    op.create_index("ix_doc_tenant", "documento_fiscal", ["tenant_id"])

    op.execute("ALTER TABLE documento_fiscal ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documento_fiscal FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON documento_fiscal"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )

    # ── tabela_simples_faixa (SCD Type 2 — nunca UPDATE) ─────────────────────
    op.create_table(
        "tabela_simples_faixa",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("anexo", sa.CHAR(3), nullable=False),
        sa.Column("faixa", sa.Integer(), nullable=False),
        sa.Column("rbt12_ate", sa.NUMERIC(14, 2), nullable=False),
        sa.Column("aliquota_nominal", sa.NUMERIC(6, 4), nullable=False),
        sa.Column("parcela_deduzir", sa.NUMERIC(14, 2), nullable=False),
        sa.Column("valid_from", sa.DATE(), nullable=False),
        sa.Column("valid_to", sa.DATE(), nullable=True),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_faixa_anexo", "tabela_simples_faixa", "anexo IN ('I','II','III','IV','V')"
    )
    op.create_check_constraint(
        "ck_faixa_numero", "tabela_simples_faixa", "faixa BETWEEN 1 AND 6"
    )
    op.create_index(
        "ix_faixa_anexo_vigente", "tabela_simples_faixa", ["anexo", "valid_from", "valid_to"]
    )

    # Seed — Resolução CGSN 140/2018 (vigente desde 2018-01-01, sem valid_to)
    _seed_tabela_simples()

    # ── apuracao_fiscal ───────────────────────────────────────────────────────
    op.create_table(
        "apuracao_fiscal",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenant.id"), nullable=False),
        sa.Column("empresa_id", sa.UUID(), sa.ForeignKey("empresa.id"), nullable=False),
        sa.Column("competencia", sa.DATE(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("regime", sa.String(50), nullable=False),
        sa.Column("input_jsonb", sa.JSON(), nullable=False),
        sa.Column("output_jsonb", sa.JSON(), nullable=False),
        sa.Column("faixas_usadas", sa.JSON(), nullable=False),
        sa.Column("algoritmo_versao", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="calculado"),
        sa.Column("transmitido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pago_em", sa.DATE(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_apuracao_tipo",
        "apuracao_fiscal",
        "tipo IN ('das','irpj','csll','pis','cofins','iss','icms','dctf','efd_contrib')",
    )
    op.create_unique_constraint(
        "uq_apuracao_empresa_comp_tipo",
        "apuracao_fiscal",
        ["empresa_id", "competencia", "tipo"],
    )
    op.create_index("ix_apuracao_tenant", "apuracao_fiscal", ["tenant_id"])
    op.create_index("ix_apuracao_empresa_comp", "apuracao_fiscal", ["empresa_id", "competencia"])

    op.execute("ALTER TABLE apuracao_fiscal ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE apuracao_fiscal FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON apuracao_fiscal"
        f" USING ({_RLS_USING})"
        f" WITH CHECK ({_RLS_USING})"
    )


def _seed_tabela_simples() -> None:
    """Insere as 30 faixas da Resolução CGSN 140/2018 (5 anexos × 6 faixas)."""
    faixas = [
        # fmt: off
        # (anexo, faixa, rbt12_ate, aliquota_nominal, parcela_deduzir, fonte)
        # Anexo I — Comércio
        ("I",   1,  180_000.00, 0.0400,       0.00, "Resolução CGSN 140/2018 Tabela I"),
        ("I",   2,  360_000.00, 0.0730,   5_940.00, "Resolução CGSN 140/2018 Tabela I"),
        ("I",   3,  720_000.00, 0.0950,  13_860.00, "Resolução CGSN 140/2018 Tabela I"),
        ("I",   4, 1_800_000.00, 0.1070,  22_500.00, "Resolução CGSN 140/2018 Tabela I"),
        ("I",   5, 3_600_000.00, 0.1430,  87_300.00, "Resolução CGSN 140/2018 Tabela I"),
        ("I",   6, 4_800_000.00, 0.1900, 378_000.00, "Resolução CGSN 140/2018 Tabela I"),
        # Anexo II — Indústria
        ("II",  1,  180_000.00, 0.0450,       0.00, "Resolução CGSN 140/2018 Tabela II"),
        ("II",  2,  360_000.00, 0.0780,   5_940.00, "Resolução CGSN 140/2018 Tabela II"),
        ("II",  3,  720_000.00, 0.1000,  13_860.00, "Resolução CGSN 140/2018 Tabela II"),
        ("II",  4, 1_800_000.00, 0.1120,  22_500.00, "Resolução CGSN 140/2018 Tabela II"),
        ("II",  5, 3_600_000.00, 0.1470,  85_500.00, "Resolução CGSN 140/2018 Tabela II"),
        ("II",  6, 4_800_000.00, 0.3000, 720_000.00, "Resolução CGSN 140/2018 Tabela II"),
        # Anexo III — Serviços (Fator R ≥ 28%)
        ("III", 1,  180_000.00, 0.0600,       0.00, "Resolução CGSN 140/2018 Tabela III"),
        ("III", 2,  360_000.00, 0.1120,   9_360.00, "Resolução CGSN 140/2018 Tabela III"),
        ("III", 3,  720_000.00, 0.1350,  17_640.00, "Resolução CGSN 140/2018 Tabela III"),
        ("III", 4, 1_800_000.00, 0.1600,  35_640.00, "Resolução CGSN 140/2018 Tabela III"),
        ("III", 5, 3_600_000.00, 0.2100, 125_640.00, "Resolução CGSN 140/2018 Tabela III"),
        ("III", 6, 4_800_000.00, 0.3300, 648_000.00, "Resolução CGSN 140/2018 Tabela III"),
        # Anexo IV — Serviços sem INSS embutido
        ("IV",  1,  180_000.00, 0.0450,       0.00, "Resolução CGSN 140/2018 Tabela IV"),
        ("IV",  2,  360_000.00, 0.0900,   8_100.00, "Resolução CGSN 140/2018 Tabela IV"),
        ("IV",  3,  720_000.00, 0.1020,  12_420.00, "Resolução CGSN 140/2018 Tabela IV"),
        ("IV",  4, 1_800_000.00, 0.1400,  39_780.00, "Resolução CGSN 140/2018 Tabela IV"),
        ("IV",  5, 3_600_000.00, 0.2200, 183_780.00, "Resolução CGSN 140/2018 Tabela IV"),
        ("IV",  6, 4_800_000.00, 0.3300, 828_000.00, "Resolução CGSN 140/2018 Tabela IV"),
        # Anexo V — Serviços (Fator R < 28%)
        ("V",   1,  180_000.00, 0.1550,       0.00, "Resolução CGSN 140/2018 Tabela V"),
        ("V",   2,  360_000.00, 0.1800,   4_500.00, "Resolução CGSN 140/2018 Tabela V"),
        ("V",   3,  720_000.00, 0.1950,   9_900.00, "Resolução CGSN 140/2018 Tabela V"),
        ("V",   4, 1_800_000.00, 0.2050,  17_100.00, "Resolução CGSN 140/2018 Tabela V"),
        ("V",   5, 3_600_000.00, 0.2300,  62_100.00, "Resolução CGSN 140/2018 Tabela V"),
        ("V",   6, 4_800_000.00, 0.3050, 540_000.00, "Resolução CGSN 140/2018 Tabela V"),
        # fmt: on
    ]
    for anexo, faixa, rbt12_ate, aliq, parcela, fonte in faixas:
        op.execute(
            sa.text(
                "INSERT INTO tabela_simples_faixa "
                "(id, anexo, faixa, rbt12_ate, aliquota_nominal, parcela_deduzir, "
                "valid_from, valid_to, fonte) VALUES "
                "(gen_random_uuid(), :anexo, :faixa, :rbt12_ate, :aliq, :parcela, "
                "'2018-01-01', NULL, :fonte)"
            ).bindparams(
                anexo=anexo,
                faixa=faixa,
                rbt12_ate=rbt12_ate,
                aliq=aliq,
                parcela=parcela,
                fonte=fonte,
            )
        )


def downgrade() -> None:
    op.drop_table("apuracao_fiscal")
    op.drop_table("tabela_simples_faixa")
    op.drop_table("documento_fiscal")
