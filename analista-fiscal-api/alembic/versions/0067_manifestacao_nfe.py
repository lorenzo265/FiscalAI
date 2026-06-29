"""Manifestação do Destinatário de NF-e (MD-e) — PR1 fundação.

Revision ID: 0067
Revises: 0066
Create Date: 2026-06-29

Tabela ``manifestacao_nfe``:
  * Uma linha por (empresa, chave_nfe, tipo_evento, sequencial).
  * UNIQUE composto garante idempotência operacional (§8.9).
  * RLS multi-tenant via ``_RLS_USING`` padrão (§8.1).

4 tipos de evento MD-e conforme NT 2014.002 / NT 2020.001:
  210200 — Confirmação da Operação
  210210 — Ciência da Operação
  210220 — Desconhecimento da Operação
  210240 — Operação não Realizada  (requer justificativa 15–255 chars)

Status machine: preparado → assinado → transmitido → aceito/rejeitado

``cOrgao = 91`` (Ambiente Nacional) — obrigação da NT, não configura por UF.

§8.2 — append-only: cancelamento real gera novo evento de anulação no
SEFAZ (protocolo da SEFAZ), não UPDATE nesta tabela. A linha permanece
com seu status final (aceito/rejeitado) como fato imutável.

§8.12 — transmissão é ato consciente: o service assina e persiste o XML,
mas a transmissão efetiva (envio ao webservice SEFAZ) é delegada ao PR3.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "manifestacao_nfe",
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
        # Chave de acesso NF-e — 44 dígitos (NT 2014.002 §4.1.1.2)
        sa.Column("chave_nfe", sa.String(44), nullable=False),
        # CNPJ do destinatário que manifesta (14 dígitos sem máscara)
        sa.Column("cnpj_destinatario", sa.String(14), nullable=False),
        # tpEvento: 210200/210210/210220/210240
        sa.Column("tipo_evento", sa.String(6), nullable=False),
        # nSeqEvento: começa em 1 (§4.1.1.2 — SEFAZ aceita até 20 por tipo)
        sa.Column("sequencial", sa.Integer(), nullable=False, server_default="1"),
        # xJust: obrigatório APENAS quando tipo_evento='210240' (15–255 chars)
        sa.Column("justificativa", sa.Text(), nullable=True),
        # Máquina de estados: preparado→assinado→transmitido→aceito/rejeitado
        sa.Column("status", sa.String(20), nullable=False, server_default="preparado"),
        # Protocolo de autorização retornado pela SEFAZ (pós-transmissão PR3)
        sa.Column("protocolo", sa.String(100), nullable=True),
        # cStat da resposta SEFAZ (ex.: 135 = evento registrado)
        sa.Column("codigo_status_sefaz", sa.Integer(), nullable=True),
        # xMotivo da resposta SEFAZ
        sa.Column("motivo_sefaz", sa.Text(), nullable=True),
        # Chave do XML assinado no object storage
        sa.Column("xml_evento_storage_key", sa.Text(), nullable=True),
        # Chave do XML de recibo (retProEvento) no object storage
        sa.Column("xml_recibo_storage_key", sa.Text(), nullable=True),
        # Idempotência cross-system: string opaca do caller
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        # Versão do algoritmo de geração XML (ALGORITMO_VERSAO do módulo)
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("assinado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("transmitido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("respondido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        # ── CHECKs ────────────────────────────────────────────────────────────
        sa.CheckConstraint(
            "tipo_evento IN ('210200','210210','210220','210240')",
            name="ck_manifestacao_tipo_evento",
        ),
        sa.CheckConstraint(
            "status IN ('preparado','assinado','transmitido','aceito','rejeitado')",
            name="ck_manifestacao_status",
        ),
        # Justificativa obrigatória para 210240 e proibida para os demais
        sa.CheckConstraint(
            "(tipo_evento = '210240') = (justificativa IS NOT NULL)",
            name="ck_manifestacao_just_obrigatoria",
        ),
        # xJust: 15–255 chars quando presente (NT 2014.002 §4.1.1.3)
        sa.CheckConstraint(
            "justificativa IS NULL OR "
            "(char_length(justificativa) >= 15 AND char_length(justificativa) <= 255)",
            name="ck_manifestacao_just_tamanho",
        ),
        # Chave NF-e: 44 dígitos
        sa.CheckConstraint(
            r"chave_nfe ~ '^\d{44}$'",
            name="ck_manifestacao_chave_formato",
        ),
        # CNPJ: 14 dígitos
        sa.CheckConstraint(
            r"cnpj_destinatario ~ '^\d{14}$'",
            name="ck_manifestacao_cnpj_formato",
        ),
        sa.CheckConstraint(
            "sequencial >= 1",
            name="ck_manifestacao_sequencial_positivo",
        ),
    )

    # ── Índices ───────────────────────────────────────────────────────────────
    op.create_index("ix_manifestacao_tenant", "manifestacao_nfe", ["tenant_id"])
    op.create_index(
        "ix_manifestacao_empresa_chave",
        "manifestacao_nfe",
        ["empresa_id", "chave_nfe"],
    )
    op.create_index(
        "ix_manifestacao_status",
        "manifestacao_nfe",
        ["status"],
        postgresql_where=sa.text("status NOT IN ('aceito','rejeitado')"),
    )

    # UNIQUE: 1 manifestação por (empresa, chave, tipo, sequencial)
    op.create_index(
        "uq_manifestacao_empresa_chave_tipo_seq",
        "manifestacao_nfe",
        ["empresa_id", "chave_nfe", "tipo_evento", "sequencial"],
        unique=True,
    )

    # UNIQUE fraco por idempotency_key (quando fornecido)
    op.create_index(
        "uq_manifestacao_idempotency_key",
        "manifestacao_nfe",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # ── RLS multi-tenant (§8.1) ───────────────────────────────────────────────
    # USING filtra SELECT/UPDATE/DELETE; WITH CHECK impede INSERT/UPDATE de
    # gravar linha de outro tenant. Padrão vigente (billing 0061, lgpd 0062,
    # refresh_token 0064) — não basta USING para tabela que recebe INSERT.
    op.execute("ALTER TABLE manifestacao_nfe ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY manifestacao_nfe_tenant ON manifestacao_nfe "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )
    # GRANT ao role das sessões autenticadas (get_session faz SET LOCAL ROLE
    # fiscal_app); o role superuser ``fiscal`` bypassa RLS, não precisa de GRANT.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON manifestacao_nfe TO fiscal_app"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS manifestacao_nfe_tenant ON manifestacao_nfe"
    )
    op.drop_table("manifestacao_nfe")
