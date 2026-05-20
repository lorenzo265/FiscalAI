"""Sprint 11 PR2 — ICMS por UF (SCD) + EFD-Reinf skeleton.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-17

Duas tabelas novas:

  * ``aliquota_icms_uf`` — SCD Type 2 com alíquota interna por UF (27 estados +
                          DF). Sem RLS (tabela pública compartilhada).
  * ``efd_reinf_evento`` — fila de eventos R-2010/R-4020/R-9000 (skeleton).
                          XML real fica para sprint futura — por ora persiste
                          dict JSONB. RLS multi-tenant.

Seed de ``aliquota_icms_uf`` com alíquotas internas vigentes em 2025
(CONFAZ + leis estaduais). Para alíquotas interestaduais (4%/7%/12%) a
regra é constante e implementada no algoritmo puro — não precisa SCD.

Princípios: §8.1 (RLS em efd_reinf_evento), §8.3 (SCD UFs), §8.9 (UNIQUE
parcial em efd_reinf_evento por (empresa, tipo, referencia_id)).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    _criar_aliquota_icms_uf()
    _criar_efd_reinf_evento()
    _seed_aliquotas_icms_uf()


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS efd_reinf_evento_tenant ON efd_reinf_evento")
    op.drop_table("efd_reinf_evento")
    op.drop_table("aliquota_icms_uf")


def _criar_aliquota_icms_uf() -> None:
    op.create_table(
        "aliquota_icms_uf",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("uf", sa.CHAR(2), nullable=False),
        sa.Column("aliquota_interna", sa.Numeric(6, 4), nullable=False),
        sa.Column(
            "aliquota_fecp", sa.Numeric(6, 4),
            nullable=False, server_default="0",
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "aliquota_interna >= 0 AND aliquota_interna <= 1",
            name="ck_icms_aliquota",
        ),
        sa.CheckConstraint(
            "aliquota_fecp >= 0 AND aliquota_fecp <= 1",
            name="ck_icms_fecp",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_icms_vigencia",
        ),
    )
    op.create_index(
        "ix_icms_uf_vigente", "aliquota_icms_uf",
        ["uf", "valid_from", "valid_to"],
    )


def _criar_efd_reinf_evento() -> None:
    op.create_table(
        "efd_reinf_evento",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tipo_evento", sa.String(10), nullable=False),
        sa.Column("referencia_tipo", sa.String(40), nullable=False),
        sa.Column("referencia_id", sa.UUID(), nullable=False),
        sa.Column("periodo_apuracao", sa.Date(), nullable=False),
        sa.Column(
            "valor_bruto_servico", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "ir_retido", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "pis_retido", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "cofins_retido", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "csll_retido", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="preparado",
        ),
        sa.Column("protocolo", sa.String(80), nullable=True),
        sa.Column(
            "resposta", sa.dialects.postgresql.JSONB(), nullable=True,
        ),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("transmitido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo_evento IN ('R-2010','R-2020','R-2030','R-2040','R-2050',"
            "'R-2055','R-2098','R-2099','R-3010','R-4010','R-4020','R-4040',"
            "'R-4080','R-4099','R-9000')",
            name="ck_reinf_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('preparado','transmitido','aceito','rejeitado','cancelado')",
            name="ck_reinf_status",
        ),
        sa.CheckConstraint(
            "valor_bruto_servico >= 0 AND ir_retido >= 0 AND pis_retido >= 0 "
            "AND cofins_retido >= 0 AND csll_retido >= 0",
            name="ck_reinf_valores_nao_negativos",
        ),
        sa.UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_reinf_empresa_tipo_ref",
        ),
    )
    op.create_index("ix_reinf_tenant", "efd_reinf_evento", ["tenant_id"])
    op.create_index(
        "ix_reinf_empresa_periodo", "efd_reinf_evento",
        ["empresa_id", "periodo_apuracao"],
    )
    op.execute("ALTER TABLE efd_reinf_evento ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY efd_reinf_evento_tenant ON efd_reinf_evento USING ({_RLS_USING})"
    )


def _seed_aliquotas_icms_uf() -> None:
    """Alíquotas internas vigentes em 2025 — fonte: leis estaduais CONFAZ."""
    tabela = sa.table(
        "aliquota_icms_uf",
        sa.column("uf", sa.CHAR(2)),
        sa.column("aliquota_interna", sa.Numeric),
        sa.column("aliquota_fecp", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("fonte", sa.String),
    )
    fonte_padrao = "CONFAZ + leis estaduais vigentes 2025"
    aliquotas: list[tuple[str, str, str]] = [
        # (UF, alíquota interna, FECP — quando aplicável)
        ("AC", "0.1900", "0"),
        ("AL", "0.1900", "0"),
        ("AP", "0.1800", "0"),
        ("AM", "0.2000", "0"),
        ("BA", "0.2050", "0"),       # 19% padrão + 1,5% adicional saúde
        ("CE", "0.2000", "0"),
        ("DF", "0.2000", "0"),
        ("ES", "0.1700", "0"),
        ("GO", "0.1900", "0"),
        ("MA", "0.2200", "0"),
        ("MT", "0.1700", "0"),
        ("MS", "0.1700", "0"),
        ("MG", "0.1800", "0"),
        ("PA", "0.1900", "0"),
        ("PB", "0.2000", "0"),
        ("PR", "0.1950", "0"),
        ("PE", "0.2050", "0"),
        ("PI", "0.2100", "0"),
        ("RJ", "0.2000", "0.0200"),  # 18% + FECP 2%
        ("RN", "0.1800", "0"),
        ("RS", "0.1700", "0"),
        ("RO", "0.1950", "0"),
        ("RR", "0.2000", "0"),
        ("SC", "0.1700", "0"),
        ("SP", "0.1800", "0"),
        ("SE", "0.1900", "0"),
        ("TO", "0.2000", "0"),
    ]
    op.bulk_insert(
        tabela,
        [
            {
                "uf": uf,
                "aliquota_interna": aliq,
                "aliquota_fecp": fecp,
                "valid_from": "2025-01-01",
                "valid_to": None,
                "fonte": fonte_padrao,
            }
            for uf, aliq, fecp in aliquotas
        ],
    )
