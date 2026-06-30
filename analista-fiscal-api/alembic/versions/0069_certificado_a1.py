"""Cofre de certificado A1 (.p12 ICP-Brasil) por empresa — épico cert A1.

Revision ID: 0069
Revises: 0068
Create Date: 2026-06-30

Tabela ``certificado_a1``:
  * Guarda o .p12 e a senha do cliente **cifrados em repouso** (envelope
    AES-256-GCM, §8.7) — o .p12 (binário) entra como ``cifrar(base64(bytes))``,
    a senha como ``cifrar(senha)``; ambos em colunas TEXT (token do envelope).
  * Metadados extraídos do cert no upload: CN, CNPJ do titular, validade,
    fingerprint SHA-256 (para auditoria e dedup).
  * Uma linha ATIVA por empresa (unique parcial ``WHERE ativo``); substituir
    desativa a anterior e insere a nova — histórico preservado (§8.2-spirit).
  * RLS multi-tenant via ``_RLS_USING`` padrão (§8.1).

Custódia da senha (decisão do PO 2026-06-30): a senha é guardada CIFRADA para
permitir transmissão automática/agendada (eSocial/Reinf/MD-e). O material só é
decifrado no ato do envio, via o único ponto de entrada ``carregar_cert_a1``.
Nunca aparece em log estruturado (§8.7).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "certificado_a1",
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
        # .p12 cifrado: token do envelope sobre base64(pfx_bytes). TEXT, não BYTEA.
        sa.Column("pfx_cifrado", sa.Text(), nullable=False),
        # Senha do .p12 cifrada (token do envelope). Guardada p/ transmissão auto.
        sa.Column("senha_cifrada", sa.Text(), nullable=False),
        # Subject CN do cert (ex.: "EMPRESA LTDA:12345678000190")
        sa.Column("cn_titular", sa.Text(), nullable=False),
        # CNPJ extraído do cert (SAN OID 2.16.76.1.3.3 ou sufixo do CN); 14 dígitos
        sa.Column("cnpj_titular", sa.String(14), nullable=True),
        # Validade do cert (notBefore/notAfter), aware (TIMESTAMPTZ)
        sa.Column("validade_inicio", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("validade_fim", sa.TIMESTAMP(timezone=True), nullable=False),
        # Fingerprint SHA-256 do cert (DER), hex — auditoria/dedup
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
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
        # CNPJ (quando extraído): 14 dígitos
        sa.CheckConstraint(
            r"cnpj_titular IS NULL OR cnpj_titular ~ '^\d{14}$'",
            name="ck_certificado_a1_cnpj_formato",
        ),
        # validade coerente
        sa.CheckConstraint(
            "validade_fim > validade_inicio",
            name="ck_certificado_a1_validade",
        ),
    )

    op.create_index("ix_certificado_a1_tenant", "certificado_a1", ["tenant_id"])

    # Apenas UMA linha ativa por empresa (substituição desativa a anterior).
    op.create_index(
        "uq_certificado_a1_empresa_ativo",
        "certificado_a1",
        ["empresa_id"],
        unique=True,
        postgresql_where=sa.text("ativo"),
    )

    # ── RLS multi-tenant (§8.1) ───────────────────────────────────────────────
    # USING filtra SELECT/UPDATE/DELETE; WITH CHECK impede INSERT/UPDATE de
    # gravar linha de outro tenant. Padrão vigente (billing 0061, manifestacao
    # 0067) — não basta USING para tabela que recebe INSERT.
    op.execute("ALTER TABLE certificado_a1 ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY certificado_a1_tenant ON certificado_a1 "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON certificado_a1 TO fiscal_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS certificado_a1_tenant ON certificado_a1")
    op.drop_table("certificado_a1")
