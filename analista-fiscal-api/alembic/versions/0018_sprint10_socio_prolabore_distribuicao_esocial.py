"""Sprint 10 PR3 — sócios, pró-labore, distribuição de lucros, eSocial.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-17

Quatro tabelas novas (Plano §5.7 + §11):

  * ``socio``                — cadastro de sócios (separado de funcionario CLT).
  * ``prolabore_mensal``     — INSS 11% (contribuinte individual) + IRRF mensal.
  * ``distribuicao_lucros``  — Lei 9.249/1995: isento até limite contábil.
  * ``evento_esocial``       — fila de eventos S-1200/S-1210/S-2200/S-2299/S-2400
                                (skeleton — XML real fica para sprint futura).

Princípios aplicados:
  §8.1  RLS em todas as 4 tabelas.
  §8.2  prolabore_mensal e distribuicao_lucros são fatos imutáveis após persistir
        (sem UPDATE direto — cancelamento gera nova linha).
  §8.9  UNIQUE composto para idempotência:
          prolabore_mensal: (socio, competencia)
          evento_esocial:   (empresa, tipo_evento, referencia_id)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    _criar_socio()
    _criar_prolabore()
    _criar_distribuicao()
    _criar_evento_esocial()


def downgrade() -> None:
    for tabela in ("evento_esocial", "distribuicao_lucros", "prolabore_mensal", "socio"):
        op.execute(f"DROP POLICY IF EXISTS {tabela}_tenant ON {tabela}")
        op.drop_table(tabela)


def _criar_socio() -> None:
    op.create_table(
        "socio",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=False),
        sa.Column(
            "percentual_participacao", sa.Numeric(7, 4), nullable=False,
            server_default="0",
        ),
        sa.Column("data_entrada", sa.Date(), nullable=False),
        sa.Column("data_saida", sa.Date(), nullable=True),
        sa.Column("dependentes_irrf", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "atualizado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(cpf) = 11 AND cpf ~ '^[0-9]+$'",
            name="ck_socio_cpf_formato",
        ),
        sa.CheckConstraint(
            "percentual_participacao >= 0 AND percentual_participacao <= 100",
            name="ck_socio_participacao",
        ),
        sa.CheckConstraint(
            "dependentes_irrf >= 0", name="ck_socio_dependentes",
        ),
        sa.CheckConstraint(
            "data_saida IS NULL OR data_saida >= data_entrada",
            name="ck_socio_saida_posterior",
        ),
        sa.UniqueConstraint("empresa_id", "cpf", name="uq_socio_empresa_cpf"),
    )
    op.create_index("ix_socio_tenant", "socio", ["tenant_id"])
    op.create_index("ix_socio_empresa_ativo", "socio", ["empresa_id", "ativo"])
    op.execute("ALTER TABLE socio ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY socio_tenant ON socio USING ({_RLS_USING})")


def _criar_prolabore() -> None:
    op.create_table(
        "prolabore_mensal",
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
            "socio_id", sa.UUID(),
            sa.ForeignKey("socio.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("valor_bruto", sa.Numeric(14, 2), nullable=False),
        sa.Column("base_inss", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "aliquota_inss", sa.Numeric(6, 4), nullable=False,
            server_default="0.1100",
        ),
        sa.Column("inss_socio", sa.Numeric(14, 2), nullable=False),
        sa.Column("base_irrf", sa.Numeric(14, 2), nullable=False),
        sa.Column("irrf", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("irrf_faixa", sa.Integer(), nullable=False),
        sa.Column("valor_liquido", sa.Numeric(14, 2), nullable=False),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "valor_bruto >= 0 AND base_inss >= 0 AND inss_socio >= 0 "
            "AND base_irrf >= 0 AND irrf >= 0 AND valor_liquido >= 0",
            name="ck_prolabore_valores_nao_negativos",
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM competencia) = 1",
            name="ck_prolabore_competencia_dia1",
        ),
        sa.CheckConstraint(
            "irrf_faixa BETWEEN 1 AND 5", name="ck_prolabore_irrf_faixa",
        ),
        sa.UniqueConstraint(
            "socio_id", "competencia", name="uq_prolabore_socio_competencia",
        ),
    )
    op.create_index("ix_prolabore_tenant", "prolabore_mensal", ["tenant_id"])
    op.create_index(
        "ix_prolabore_empresa_comp", "prolabore_mensal",
        ["empresa_id", "competencia"],
    )
    op.execute("ALTER TABLE prolabore_mensal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY prolabore_mensal_tenant ON prolabore_mensal "
        f"USING ({_RLS_USING})"
    )


def _criar_distribuicao() -> None:
    op.create_table(
        "distribuicao_lucros",
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
            "socio_id", sa.UUID(),
            sa.ForeignKey("socio.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("data_distribuicao", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("limite_isento_apurado", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_isento", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "valor_tributavel", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "irrf_retido", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("base_calculo_referencia", sa.String(40), nullable=False),
        sa.Column("algoritmo_versao", sa.String(30), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "valor >= 0 AND limite_isento_apurado >= 0 AND valor_isento >= 0 "
            "AND valor_tributavel >= 0 AND irrf_retido >= 0",
            name="ck_distribuicao_valores_nao_negativos",
        ),
        sa.CheckConstraint(
            "valor_isento + valor_tributavel = valor",
            name="ck_distribuicao_soma_consistente",
        ),
        sa.CheckConstraint(
            "base_calculo_referencia IN ('presuncao_lp','simples_dentro_das',"
            "'lucro_contabil','mei')",
            name="ck_distribuicao_base",
        ),
    )
    op.create_index("ix_distribuicao_tenant", "distribuicao_lucros", ["tenant_id"])
    op.create_index(
        "ix_distribuicao_socio_data", "distribuicao_lucros",
        ["socio_id", "data_distribuicao"],
    )
    op.execute("ALTER TABLE distribuicao_lucros ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY distribuicao_lucros_tenant ON distribuicao_lucros "
        f"USING ({_RLS_USING})"
    )


def _criar_evento_esocial() -> None:
    op.create_table(
        "evento_esocial",
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
        sa.Column("periodo_apuracao", sa.Date(), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default="preparado",
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
        sa.Column("processado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo_evento IN ('S-1200','S-1210','S-2200','S-2299','S-2400')",
            name="ck_esocial_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('preparado','transmitido','aceito','rejeitado','cancelado')",
            name="ck_esocial_status",
        ),
        sa.UniqueConstraint(
            "empresa_id", "tipo_evento", "referencia_id",
            name="uq_esocial_empresa_tipo_ref",
        ),
    )
    op.create_index("ix_esocial_tenant", "evento_esocial", ["tenant_id"])
    op.create_index(
        "ix_esocial_empresa_periodo", "evento_esocial",
        ["empresa_id", "periodo_apuracao"],
    )
    op.execute("ALTER TABLE evento_esocial ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY evento_esocial_tenant ON evento_esocial USING ({_RLS_USING})"
    )
