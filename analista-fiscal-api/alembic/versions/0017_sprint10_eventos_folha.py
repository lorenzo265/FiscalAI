"""Sprint 10 PR2 — eventos de folha (13º, férias, rescisão).

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-17

Cria a tabela ``evento_folha`` — fato imutável para pagamentos pontuais
fora do holerite mensal padrão. Tipos cobertos:

  * ``13_primeira``  — 1ª parcela do 13º (sem desconto INSS/IRRF).
  * ``13_segunda``   — 2ª parcela (com INSS escalonado + IRRF separado).
  * ``ferias``       — férias gozadas + 1/3 + abono pecuniário (isento).
  * ``rescisao``     — verbas rescisórias + multa FGTS.

Snapshot completo do cálculo vai em ``detalhes`` JSONB (alíquotas usadas,
parcelas a deduzir, FGTS por verba, etc.) — preserva auditoria mesmo se
tabelas SCD mudarem depois (§8.3).

Idempotência (§8.9):
  * 13º:      UNIQUE (funcionario, tipo, ano_referencia) parcial.
  * Férias:   UNIQUE (funcionario, tipo, periodo_inicio) parcial.
  * Rescisão: UNIQUE (funcionario, tipo) parcial — só pode haver 1.

Princípios: §8.1 (RLS), §8.2 (imutável), §8.9 (UNIQUE), §8.10 (audit).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "evento_folha",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "funcionario_id", sa.UUID(),
            sa.ForeignKey("funcionario.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("data_evento", sa.Date(), nullable=False),
        sa.Column("ano_referencia", sa.Integer(), nullable=True),
        sa.Column("periodo_inicio", sa.Date(), nullable=True),
        sa.Column("periodo_fim", sa.Date(), nullable=True),
        sa.Column("valor_bruto", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "inss_empregado", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("irrf", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "fgts_empregador", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "multa_fgts", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("valor_liquido", sa.Numeric(14, 2), nullable=False),
        sa.Column("detalhes", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('13_primeira','13_segunda','ferias','rescisao')",
            name="ck_evento_tipo",
        ),
        sa.CheckConstraint(
            "valor_bruto >= 0 AND inss_empregado >= 0 AND irrf >= 0 "
            "AND fgts_empregador >= 0 AND multa_fgts >= 0",
            name="ck_evento_valores_nao_negativos",
        ),
        sa.CheckConstraint(
            "(tipo LIKE '13_%' AND ano_referencia IS NOT NULL) OR tipo NOT LIKE '13_%'",
            name="ck_evento_13_tem_ano",
        ),
        sa.CheckConstraint(
            "(tipo = 'ferias' AND periodo_inicio IS NOT NULL AND periodo_fim IS NOT NULL) "
            "OR tipo <> 'ferias'",
            name="ck_evento_ferias_tem_periodo",
        ),
    )
    op.create_index("ix_evento_tenant", "evento_folha", ["tenant_id"])
    op.create_index(
        "ix_evento_func_data", "evento_folha",
        ["funcionario_id", "data_evento"],
    )

    # Idempotência por tipo (UNIQUE parciais).
    op.create_index(
        "uq_evento_13", "evento_folha",
        ["funcionario_id", "tipo", "ano_referencia"],
        unique=True,
        postgresql_where=sa.text("tipo IN ('13_primeira','13_segunda')"),
    )
    op.create_index(
        "uq_evento_ferias", "evento_folha",
        ["funcionario_id", "tipo", "periodo_inicio"],
        unique=True,
        postgresql_where=sa.text("tipo = 'ferias'"),
    )
    op.create_index(
        "uq_evento_rescisao", "evento_folha",
        ["funcionario_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("tipo = 'rescisao'"),
    )

    op.execute("ALTER TABLE evento_folha ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY evento_folha_tenant ON evento_folha USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS evento_folha_tenant ON evento_folha")
    op.drop_table("evento_folha")
