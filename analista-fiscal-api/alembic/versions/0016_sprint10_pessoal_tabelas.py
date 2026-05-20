"""Sprint 10 PR1 — pessoal (folha) + tabelas tributárias INSS/IRRF/FGTS.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-17

Cria infra de Departamento Pessoal:

  * ``funcionario`` — cadastro CLT (sócio/pró-labore ficam na Sprint 10 PR3).
  * ``folha_mensal`` — cabeçalho da folha (totais + status aberta/fechada).
  * ``holerite``     — linha por funcionário dentro de uma folha (snapshot
                       do cálculo). Fato imutável após folha fechar (§8.2).

Tabelas tributárias SCD Type 2 (§8.3) — populadas com valores vigentes:

  * ``tabela_inss_faixa``  — 4 faixas progressivas (Portaria MPS/MF 6/2025).
  * ``tabela_irrf_faixa``  — 5 faixas + dedução por dependente
                              (Lei 14.848/2024 + MP 1.171/2024, vigência fev/2024).
  * ``tabela_fgts_aliquota`` — alíquota por vínculo (Lei 8.036/1990).

Quando a Portaria 2026 oficial for publicada, insere-se nova linha com
``valid_from='2026-XX-XX'`` e fecha-se a anterior — sem mexer no histórico.

Princípios aplicados: §8.1 (RLS multi-tenant nas 3 tabelas operacionais),
§8.2 (folha fechada vira fato imutável — UPDATE bloqueado por status),
§8.3 (SCD nas 3 tabelas tributárias), §8.9 (UNIQUE garantindo idempotência).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    _criar_funcionario()
    _criar_folha_mensal()
    _criar_holerite()
    _criar_tabela_inss()
    _criar_tabela_irrf()
    _criar_tabela_fgts()
    _seed_tabelas_2025()


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS holerite_tenant ON holerite")
    op.execute("DROP POLICY IF EXISTS folha_mensal_tenant ON folha_mensal")
    op.execute("DROP POLICY IF EXISTS funcionario_tenant ON funcionario")
    op.drop_table("holerite")
    op.drop_table("folha_mensal")
    op.drop_table("funcionario")
    op.drop_table("tabela_fgts_aliquota")
    op.drop_table("tabela_irrf_faixa")
    op.drop_table("tabela_inss_faixa")


# ── Domínio (com RLS) ──────────────────────────────────────────────────────


def _criar_funcionario() -> None:
    op.create_table(
        "funcionario",
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
        sa.Column("cargo", sa.String(120), nullable=True),
        sa.Column("vinculo", sa.String(30), nullable=False, server_default="clt"),
        sa.Column("data_admissao", sa.Date(), nullable=False),
        sa.Column("data_demissao", sa.Date(), nullable=True),
        sa.Column("salario_base", sa.Numeric(14, 2), nullable=False),
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
            "vinculo IN ('clt','prazo_determinado','intermitente')",
            name="ck_funcionario_vinculo",
        ),
        sa.CheckConstraint("salario_base >= 0", name="ck_funcionario_salario_nao_negativo"),
        sa.CheckConstraint(
            "dependentes_irrf >= 0", name="ck_funcionario_dependentes_nao_negativo",
        ),
        sa.CheckConstraint(
            "char_length(cpf) = 11 AND cpf ~ '^[0-9]+$'",
            name="ck_funcionario_cpf_formato",
        ),
        sa.CheckConstraint(
            "data_demissao IS NULL OR data_demissao >= data_admissao",
            name="ck_funcionario_demissao_posterior",
        ),
        sa.UniqueConstraint("empresa_id", "cpf", name="uq_funcionario_empresa_cpf"),
    )
    op.create_index("ix_funcionario_tenant", "funcionario", ["tenant_id"])
    op.create_index(
        "ix_funcionario_empresa_ativo", "funcionario",
        ["empresa_id", "ativo"],
    )
    op.execute("ALTER TABLE funcionario ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY funcionario_tenant ON funcionario USING ({_RLS_USING})"
    )


def _criar_folha_mensal() -> None:
    op.create_table(
        "folha_mensal",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="aberta"),
        sa.Column(
            "total_proventos", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column(
            "total_descontos", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column(
            "total_inss_empregado", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column(
            "total_irrf", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column(
            "total_fgts_empregador", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column(
            "total_liquido", sa.Numeric(14, 2), nullable=False, server_default="0",
        ),
        sa.Column("qtd_funcionarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("algoritmo_versao", sa.String(20), nullable=True),
        sa.Column("fechada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('aberta','fechada')", name="ck_folha_status",
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM competencia) = 1",
            name="ck_folha_competencia_dia1",
        ),
        sa.CheckConstraint(
            "(status = 'fechada' AND fechada_em IS NOT NULL AND algoritmo_versao IS NOT NULL) "
            "OR status = 'aberta'",
            name="ck_folha_fechada_completa",
        ),
        sa.UniqueConstraint(
            "empresa_id", "competencia", name="uq_folha_empresa_competencia",
        ),
    )
    op.create_index("ix_folha_tenant", "folha_mensal", ["tenant_id"])
    op.create_index(
        "ix_folha_empresa_comp", "folha_mensal", ["empresa_id", "competencia"],
    )
    op.execute("ALTER TABLE folha_mensal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY folha_mensal_tenant ON folha_mensal USING ({_RLS_USING})"
    )


def _criar_holerite() -> None:
    op.create_table(
        "holerite",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "folha_mensal_id", sa.UUID(),
            sa.ForeignKey("folha_mensal.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "funcionario_id", sa.UUID(),
            sa.ForeignKey("funcionario.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("salario_base", sa.Numeric(14, 2), nullable=False),
        sa.Column("salario_bruto", sa.Numeric(14, 2), nullable=False),
        sa.Column("inss_empregado", sa.Numeric(14, 2), nullable=False),
        sa.Column("inss_aliquota_efetiva", sa.Numeric(6, 4), nullable=False),
        sa.Column("dependentes_irrf", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "deducao_dependentes_irrf", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("base_irrf", sa.Numeric(14, 2), nullable=False),
        sa.Column("irrf", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("irrf_faixa", sa.Integer(), nullable=False),
        sa.Column("fgts_empregador", sa.Numeric(14, 2), nullable=False),
        sa.Column("fgts_aliquota", sa.Numeric(6, 4), nullable=False),
        sa.Column("valor_liquido", sa.Numeric(14, 2), nullable=False),
        sa.Column("algoritmo_versao", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "salario_base >= 0 AND salario_bruto >= 0 AND inss_empregado >= 0 "
            "AND base_irrf >= 0 AND irrf >= 0 AND fgts_empregador >= 0 "
            "AND valor_liquido >= 0",
            name="ck_holerite_valores_nao_negativos",
        ),
        sa.CheckConstraint(
            "irrf_faixa BETWEEN 1 AND 5", name="ck_holerite_irrf_faixa",
        ),
        sa.UniqueConstraint(
            "folha_mensal_id", "funcionario_id", name="uq_holerite_folha_func",
        ),
    )
    op.create_index("ix_holerite_tenant", "holerite", ["tenant_id"])
    op.create_index(
        "ix_holerite_funcionario_comp", "holerite",
        ["funcionario_id", "competencia"],
    )
    op.execute("ALTER TABLE holerite ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY holerite_tenant ON holerite USING ({_RLS_USING})"
    )


# ── Tabelas tributárias (SCD Type 2, sem RLS) ──────────────────────────────


def _criar_tabela_inss() -> None:
    op.create_table(
        "tabela_inss_faixa",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("faixa", sa.Integer(), nullable=False),
        sa.Column("valor_ate", sa.Numeric(14, 2), nullable=False),
        sa.Column("aliquota", sa.Numeric(6, 4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('empregado','contribuinte_individual')",
            name="ck_inss_tipo",
        ),
        sa.CheckConstraint("faixa BETWEEN 1 AND 4", name="ck_inss_faixa"),
        sa.CheckConstraint(
            "aliquota >= 0 AND aliquota <= 1", name="ck_inss_aliquota",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_inss_vigencia",
        ),
    )
    op.create_index(
        "ix_inss_tipo_vigente", "tabela_inss_faixa",
        ["tipo", "valid_from", "valid_to"],
    )


def _criar_tabela_irrf() -> None:
    op.create_table(
        "tabela_irrf_faixa",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("faixa", sa.Integer(), nullable=False),
        sa.Column("base_ate", sa.Numeric(14, 2), nullable=False),
        sa.Column("aliquota", sa.Numeric(6, 4), nullable=False),
        sa.Column("parcela_deduzir", sa.Numeric(14, 2), nullable=False),
        sa.Column("deducao_dependente", sa.Numeric(14, 2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint("faixa BETWEEN 1 AND 5", name="ck_irrf_faixa"),
        sa.CheckConstraint(
            "aliquota >= 0 AND aliquota <= 1", name="ck_irrf_aliquota",
        ),
        sa.CheckConstraint(
            "parcela_deduzir >= 0 AND deducao_dependente >= 0",
            name="ck_irrf_deducoes",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_irrf_vigencia",
        ),
    )
    op.create_index(
        "ix_irrf_vigente", "tabela_irrf_faixa",
        ["valid_from", "valid_to"],
    )


def _criar_tabela_fgts() -> None:
    op.create_table(
        "tabela_fgts_aliquota",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("vinculo", sa.String(30), nullable=False),
        sa.Column("aliquota", sa.Numeric(6, 4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "vinculo IN ('clt','jovem_aprendiz','domestico')",
            name="ck_fgts_vinculo",
        ),
        sa.CheckConstraint(
            "aliquota >= 0 AND aliquota <= 1", name="ck_fgts_aliquota",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_fgts_vigencia",
        ),
    )
    op.create_index(
        "ix_fgts_vinculo_vigente", "tabela_fgts_aliquota",
        ["vinculo", "valid_from", "valid_to"],
    )


# ── Seed das tabelas tributárias vigentes ──────────────────────────────────


def _seed_tabelas_2025() -> None:
    """Insere os valores tributários vigentes em 2025.

    INSS empregado: Portaria Interministerial MPS/MF nº 6/2025.
    IRRF: Lei 14.848/2024 + MP 1.171/2024 (vigência fev/2024).
    FGTS: Lei 8.036/1990 art. 15 (CLT 8%) + LC 150/2015 (doméstico 8%) +
          Lei 10.097/2000 (jovem aprendiz 2%).
    """
    inss_t = sa.table(
        "tabela_inss_faixa",
        sa.column("tipo", sa.String),
        sa.column("faixa", sa.Integer),
        sa.column("valor_ate", sa.Numeric),
        sa.column("aliquota", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("fonte", sa.String),
    )
    fonte_inss = "Portaria Interministerial MPS/MF nº 6/2025"
    op.bulk_insert(
        inss_t,
        [
            {
                "tipo": "empregado", "faixa": 1,
                "valor_ate": "1518.00", "aliquota": "0.0750",
                "valid_from": "2025-01-01", "valid_to": None, "fonte": fonte_inss,
            },
            {
                "tipo": "empregado", "faixa": 2,
                "valor_ate": "2793.88", "aliquota": "0.0900",
                "valid_from": "2025-01-01", "valid_to": None, "fonte": fonte_inss,
            },
            {
                "tipo": "empregado", "faixa": 3,
                "valor_ate": "4190.83", "aliquota": "0.1200",
                "valid_from": "2025-01-01", "valid_to": None, "fonte": fonte_inss,
            },
            {
                "tipo": "empregado", "faixa": 4,
                "valor_ate": "8157.41", "aliquota": "0.1400",
                "valid_from": "2025-01-01", "valid_to": None, "fonte": fonte_inss,
            },
            # contribuinte_individual (sócio, autônomo) — alíquota plana 11%
            # até o teto. Persistido como faixa única para uso em pró-labore
            # (Sprint 10 PR3).
            {
                "tipo": "contribuinte_individual", "faixa": 1,
                "valor_ate": "8157.41", "aliquota": "0.1100",
                "valid_from": "2025-01-01", "valid_to": None,
                "fonte": "Lei 8.212/1991 art. 21 + " + fonte_inss,
            },
        ],
    )

    irrf_t = sa.table(
        "tabela_irrf_faixa",
        sa.column("faixa", sa.Integer),
        sa.column("base_ate", sa.Numeric),
        sa.column("aliquota", sa.Numeric),
        sa.column("parcela_deduzir", sa.Numeric),
        sa.column("deducao_dependente", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("fonte", sa.String),
    )
    fonte_irrf = "Lei 14.848/2024 + MP 1.171/2024 (vigência fev/2024)"
    dep = "189.59"
    teto_simbolico = "999999999.99"  # representa "acima de base_ate da faixa 4"
    op.bulk_insert(
        irrf_t,
        [
            {
                "faixa": 1, "base_ate": "2259.20", "aliquota": "0.0000",
                "parcela_deduzir": "0.00", "deducao_dependente": dep,
                "valid_from": "2024-02-01", "valid_to": None, "fonte": fonte_irrf,
            },
            {
                "faixa": 2, "base_ate": "2826.65", "aliquota": "0.0750",
                "parcela_deduzir": "169.44", "deducao_dependente": dep,
                "valid_from": "2024-02-01", "valid_to": None, "fonte": fonte_irrf,
            },
            {
                "faixa": 3, "base_ate": "3751.05", "aliquota": "0.1500",
                "parcela_deduzir": "381.44", "deducao_dependente": dep,
                "valid_from": "2024-02-01", "valid_to": None, "fonte": fonte_irrf,
            },
            {
                "faixa": 4, "base_ate": "4664.68", "aliquota": "0.2250",
                "parcela_deduzir": "662.77", "deducao_dependente": dep,
                "valid_from": "2024-02-01", "valid_to": None, "fonte": fonte_irrf,
            },
            {
                "faixa": 5, "base_ate": teto_simbolico, "aliquota": "0.2750",
                "parcela_deduzir": "896.00", "deducao_dependente": dep,
                "valid_from": "2024-02-01", "valid_to": None, "fonte": fonte_irrf,
            },
        ],
    )

    fgts_t = sa.table(
        "tabela_fgts_aliquota",
        sa.column("vinculo", sa.String),
        sa.column("aliquota", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("fonte", sa.String),
    )
    op.bulk_insert(
        fgts_t,
        [
            {
                "vinculo": "clt", "aliquota": "0.0800",
                "valid_from": "1990-05-11", "valid_to": None,
                "fonte": "Lei 8.036/1990 art. 15",
            },
            {
                "vinculo": "domestico", "aliquota": "0.0800",
                "valid_from": "2015-06-02", "valid_to": None,
                "fonte": "LC 150/2015 art. 34",
            },
            {
                "vinculo": "jovem_aprendiz", "aliquota": "0.0200",
                "valid_from": "2000-12-19", "valid_to": None,
                "fonte": "Lei 10.097/2000 + Decreto 5.598/2005",
            },
        ],
    )
