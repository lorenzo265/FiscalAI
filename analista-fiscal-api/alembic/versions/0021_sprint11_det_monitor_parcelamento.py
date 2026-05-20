"""Sprint 11 PR3 — DET + monitor cadastral RFB/Sintegra + parcelamentos.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-17

Quatro tabelas com RLS multi-tenant (§8.1):

  * ``mensagem_det``           — caixa postal Domicílio Eletrônico Trabalhista
                                  (espelha o pattern de ``mensagem_e_cac``).
  * ``status_cadastral_rfb``   — snapshot da situação cadastral CNPJ na RFB
                                  (ativo/suspenso/baixado, restrições).
  * ``status_sintegra``        — snapshot da inscrição estadual (habilitada,
                                  cancelada, inapta), por UF.
  * ``parcelamento_fiscal``    — pedidos de parcelamento (ordinário Lei
                                  10.522/2002, PERT, PERT2 etc.).
  * ``parcela_fiscal``         — linhas mensais do parcelamento.

Princípios: §8.1 (RLS), §8.2 (snapshots imutáveis — nova linha por sync),
§8.9 (UNIQUE para idempotência).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    _criar_mensagem_det()
    _criar_status_cadastral_rfb()
    _criar_status_sintegra()
    _criar_parcelamento()
    _criar_parcela()


def downgrade() -> None:
    for t in (
        "parcela_fiscal", "parcelamento_fiscal",
        "status_sintegra", "status_cadastral_rfb", "mensagem_det",
    ):
        op.execute(f"DROP POLICY IF EXISTS {t}_tenant ON {t}")
        op.drop_table(t)


def _criar_mensagem_det() -> None:
    op.create_table(
        "mensagem_det",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("id_externo_det", sa.String(80), nullable=False),
        sa.Column("assunto", sa.String(255), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=True),
        sa.Column(
            "origem", sa.String(50),
            nullable=False, server_default="MTE",
        ),
        sa.Column("recebida_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lida_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=True),
        sa.Column("prioridade", sa.String(10), nullable=True),
        sa.Column("prazo_resposta", sa.Date(), nullable=True),
        sa.Column("classificada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("classificador_versao", sa.String(40), nullable=True),
        sa.Column(
            "encaminhada_marketplace", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IS NULL OR tipo IN ('notificacao','autuacao','aviso','informativa','outro')",
            name="ck_det_tipo",
        ),
        sa.CheckConstraint(
            "prioridade IS NULL OR prioridade IN ('alta','media','baixa')",
            name="ck_det_prioridade",
        ),
        sa.UniqueConstraint(
            "empresa_id", "id_externo_det", name="uq_det_idempotente",
        ),
    )
    op.create_index("ix_det_tenant", "mensagem_det", ["tenant_id"])
    op.create_index(
        "ix_det_empresa_recebida", "mensagem_det",
        ["empresa_id", "recebida_em"],
    )
    op.execute("ALTER TABLE mensagem_det ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY mensagem_det_tenant ON mensagem_det USING ({_RLS_USING})")


def _criar_status_cadastral_rfb() -> None:
    op.create_table(
        "status_cadastral_rfb",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("consultado_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("situacao_cadastral", sa.String(40), nullable=False),
        sa.Column("data_situacao", sa.Date(), nullable=True),
        sa.Column("motivo_situacao", sa.String(255), nullable=True),
        sa.Column(
            "restricoes", sa.dialects.postgresql.JSONB(), nullable=True,
        ),
        sa.Column("regime_apuracao", sa.String(50), nullable=True),
        sa.Column(
            "snapshot", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "situacao_cadastral IN ('ativa','suspensa','inapta','baixada','nula')",
            name="ck_rfb_situacao",
        ),
    )
    op.create_index("ix_rfb_tenant", "status_cadastral_rfb", ["tenant_id"])
    op.create_index(
        "ix_rfb_empresa_consultado", "status_cadastral_rfb",
        ["empresa_id", "consultado_em"],
    )
    op.execute("ALTER TABLE status_cadastral_rfb ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY status_cadastral_rfb_tenant ON status_cadastral_rfb "
        f"USING ({_RLS_USING})"
    )


def _criar_status_sintegra() -> None:
    op.create_table(
        "status_sintegra",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("uf", sa.CHAR(2), nullable=False),
        sa.Column("inscricao_estadual", sa.String(20), nullable=False),
        sa.Column("consultado_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("situacao", sa.String(40), nullable=False),
        sa.Column("data_situacao", sa.Date(), nullable=True),
        sa.Column("regime_apuracao_ie", sa.String(60), nullable=True),
        sa.Column(
            "snapshot", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "situacao IN ('habilitada','suspensa','cancelada','inapta','baixada','desconhecida')",
            name="ck_sintegra_situacao",
        ),
    )
    op.create_index("ix_sintegra_tenant", "status_sintegra", ["tenant_id"])
    op.create_index(
        "ix_sintegra_empresa_uf_consultado", "status_sintegra",
        ["empresa_id", "uf", "consultado_em"],
    )
    op.execute("ALTER TABLE status_sintegra ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY status_sintegra_tenant ON status_sintegra "
        f"USING ({_RLS_USING})"
    )


def _criar_parcelamento() -> None:
    op.create_table(
        "parcelamento_fiscal",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("identificador_externo", sa.String(80), nullable=True),
        sa.Column("data_adesao", sa.Date(), nullable=False),
        sa.Column("divida_consolidada", sa.Numeric(14, 2), nullable=False),
        sa.Column("num_parcelas", sa.Integer(), nullable=False),
        sa.Column("parcela_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ativo"),
        sa.Column(
            "cancelado_em", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.Column(
            "motivo_cancelamento", sa.String(255), nullable=True,
        ),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('ordinario','pert','pert2','simplificado','reabertura','outros')",
            name="ck_parcelamento_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('ativo','quitado','cancelado','rescindido')",
            name="ck_parcelamento_status",
        ),
        sa.CheckConstraint(
            "divida_consolidada > 0 AND parcela_base > 0 "
            "AND num_parcelas BETWEEN 1 AND 240",
            name="ck_parcelamento_valores",
        ),
    )
    op.create_index("ix_parcelamento_tenant", "parcelamento_fiscal", ["tenant_id"])
    op.create_index(
        "ix_parcelamento_empresa_status", "parcelamento_fiscal",
        ["empresa_id", "status"],
    )
    op.execute("ALTER TABLE parcelamento_fiscal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY parcelamento_fiscal_tenant ON parcelamento_fiscal "
        f"USING ({_RLS_USING})"
    )


def _criar_parcela() -> None:
    op.create_table(
        "parcela_fiscal",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "parcelamento_id", sa.UUID(),
            sa.ForeignKey("parcelamento_fiscal.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("vencimento", sa.Date(), nullable=False),
        sa.Column("valor_projetado", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_pago", sa.Numeric(14, 2), nullable=True),
        sa.Column("pago_em", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="a_pagar",
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('a_pagar','pago','atrasado','cancelado')",
            name="ck_parcela_status",
        ),
        sa.CheckConstraint(
            "numero >= 1 AND valor_projetado > 0",
            name="ck_parcela_valores",
        ),
        sa.UniqueConstraint(
            "parcelamento_id", "numero", name="uq_parcela_numero",
        ),
    )
    op.create_index("ix_parcela_tenant", "parcela_fiscal", ["tenant_id"])
    op.create_index(
        "ix_parcela_vencimento", "parcela_fiscal",
        ["vencimento", "status"],
    )
    op.execute("ALTER TABLE parcela_fiscal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY parcela_fiscal_tenant ON parcela_fiscal USING ({_RLS_USING})"
    )
