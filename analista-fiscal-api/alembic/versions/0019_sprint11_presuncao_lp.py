"""Sprint 11 PR1 — tabela SCD ``presuncao_lucro_presumido`` + seed.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-17

Cria a tabela SCD Type 2 (§8.3) com os percentuais de presunção do Lucro
Presumido por atividade — IN RFB 1.700/2017 art. 33 (consolidando Lei
9.249/1995 art. 15 e art. 20).

Seed inicial com 8 grupos cobrindo o universo da PME-alvo:

  ┌─────────────────────────────┬───────┬───────┬──────────────────────────┐
  │ Grupo                       │ IRPJ% │ CSLL% │ Base legal               │
  ├─────────────────────────────┼───────┼───────┼──────────────────────────┤
  │ revenda_combustiveis        │ 1,6%  │ 12%   │ art. 15 §1º I            │
  │ comercio_industria          │ 8%    │ 12%   │ art. 15 caput (default)  │
  │ transporte_cargas           │ 8%    │ 12%   │ art. 15 §1º II `a`       │
  │ servicos_hospitalares       │ 8%    │ 12%   │ art. 15 §1º III `a`      │
  │ transporte_passageiros      │ 16%   │ 12%   │ art. 15 §1º II `b`       │
  │ servicos_gerais_ate_120k    │ 16%   │ 12%   │ art. 15 §4º (Lei 9.250)  │
  │ servicos_profissionais      │ 32%   │ 32%   │ art. 15 §1º IV + art. 20 │
  │ intermediacao_negocios      │ 32%   │ 32%   │ art. 15 §1º IV `a`–`d`   │
  └─────────────────────────────┴───────┴───────┴──────────────────────────┘

Match por CNAE: ``cnae_pattern`` é prefixo da seção/divisão/grupo CNAE
2.3 do IBGE — o service tenta do mais específico (5 chars) para o mais
genérico (2 chars), caindo no default ``comercio_industria`` (8%/12%) se
nenhum casar.

Sem RLS (tabela pública compartilhada por todos os tenants).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "presuncao_lucro_presumido",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("grupo_atividade", sa.String(60), nullable=False),
        sa.Column("cnae_pattern", sa.String(20), nullable=True),
        sa.Column("percentual_irpj", sa.Numeric(6, 4), nullable=False),
        sa.Column("percentual_csll", sa.Numeric(6, 4), nullable=False),
        sa.Column(
            "limite_receita_anual", sa.Numeric(14, 2), nullable=True,
        ),
        sa.Column("prioridade", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("fonte", sa.String(255), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "percentual_irpj >= 0 AND percentual_irpj <= 1",
            name="ck_presuncao_irpj",
        ),
        sa.CheckConstraint(
            "percentual_csll >= 0 AND percentual_csll <= 1",
            name="ck_presuncao_csll",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_presuncao_vigencia",
        ),
    )
    op.create_index(
        "ix_presuncao_pattern_vigente", "presuncao_lucro_presumido",
        ["cnae_pattern", "valid_from", "valid_to"],
    )
    op.create_index(
        "ix_presuncao_prioridade", "presuncao_lucro_presumido",
        ["prioridade", "valid_from"],
    )

    _seed_grupos()


def downgrade() -> None:
    op.drop_table("presuncao_lucro_presumido")


def _seed_grupos() -> None:
    """Seed dos 8 grupos vigentes (IN RFB 1.700/2017 art. 33)."""
    tabela = sa.table(
        "presuncao_lucro_presumido",
        sa.column("grupo_atividade", sa.String),
        sa.column("cnae_pattern", sa.String),
        sa.column("percentual_irpj", sa.Numeric),
        sa.column("percentual_csll", sa.Numeric),
        sa.column("limite_receita_anual", sa.Numeric),
        sa.column("prioridade", sa.Integer),
        sa.column("fonte", sa.String),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
    )
    fonte = "Lei 9.249/1995 art. 15 + art. 20 + IN RFB 1.700/2017 art. 33"
    rows = [
        # ─── Default (sem CNAE pattern, prioridade alta = peso baixo) ───────
        {
            "grupo_atividade": "comercio_industria",
            "cnae_pattern": None, "percentual_irpj": "0.0800",
            "percentual_csll": "0.1200", "limite_receita_anual": None,
            "prioridade": 99, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Revenda de combustíveis (1,6% IRPJ) ───────────────────────────
        {
            "grupo_atividade": "revenda_combustiveis",
            "cnae_pattern": "47.30", "percentual_irpj": "0.0160",
            "percentual_csll": "0.1200", "limite_receita_anual": None,
            "prioridade": 10, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Transporte de cargas (8%) ─────────────────────────────────────
        {
            "grupo_atividade": "transporte_cargas",
            "cnae_pattern": "49.30", "percentual_irpj": "0.0800",
            "percentual_csll": "0.1200", "limite_receita_anual": None,
            "prioridade": 20, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Serviços hospitalares (8%) ────────────────────────────────────
        {
            "grupo_atividade": "servicos_hospitalares",
            "cnae_pattern": "86.10", "percentual_irpj": "0.0800",
            "percentual_csll": "0.1200", "limite_receita_anual": None,
            "prioridade": 20, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Transporte de passageiros (16%) ───────────────────────────────
        {
            "grupo_atividade": "transporte_passageiros",
            "cnae_pattern": "49.21", "percentual_irpj": "0.1600",
            "percentual_csll": "0.1200", "limite_receita_anual": None,
            "prioridade": 20, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Serviços gerais até R$120k/ano (16%) ──────────────────────────
        # Match condicional aplicado pelo service: limite_receita_anual <= 120k
        {
            "grupo_atividade": "servicos_gerais_pequenos",
            "cnae_pattern": None, "percentual_irpj": "0.1600",
            "percentual_csll": "0.1200",
            "limite_receita_anual": "120000.00",
            "prioridade": 30, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Serviços profissionais regulamentados (32%/32%) ───────────────
        # CNAE 69 (advocacia/contabilidade), 71 (eng/arquit.), 73 (publ.),
        # 75 (vet.), 85.5 (cursos), 86.2/86.3/86.9 (saúde profissional),
        # 96 (serviços pessoais)
        {
            "grupo_atividade": "servicos_profissionais",
            "cnae_pattern": "69", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        {
            "grupo_atividade": "servicos_profissionais",
            "cnae_pattern": "71", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        {
            "grupo_atividade": "servicos_profissionais",
            "cnae_pattern": "73", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        # ─── Intermediação de negócios + administração de imóveis (32%/32%) ─
        {
            "grupo_atividade": "intermediacao_negocios",
            "cnae_pattern": "70", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        {
            "grupo_atividade": "intermediacao_negocios",
            "cnae_pattern": "74", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
        {
            "grupo_atividade": "intermediacao_negocios",
            "cnae_pattern": "82", "percentual_irpj": "0.3200",
            "percentual_csll": "0.3200", "limite_receita_anual": None,
            "prioridade": 15, "fonte": fonte,
            "valid_from": "1996-01-01", "valid_to": None,
        },
    ]
    op.bulk_insert(tabela, rows)
