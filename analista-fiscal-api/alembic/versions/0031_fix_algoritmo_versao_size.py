"""Fix algoritmo_versao VARCHAR(20) → VARCHAR(50).

Bug pré-existente descoberto ao escrever teste integration: strings como
``lp.irpj.trimestral.v2`` (21 chars) eram truncadas. Aumenta para 50 em
todas as tabelas afetadas — bumps futuros (ex.: ``v10``, ``v11``) ficam
seguros sem alterar schema.

§8.3 — `algoritmo_versao` é metadata de SCD; não há risco de regressão.

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


_TABELAS = (
    "apuracao_fiscal",
    "conciliacao_match",
    "declaracao_anual",
    "distribuicao_lucros",
    "efd_reinf_evento",
    "evento_esocial",
    "evento_folha",
    "folha_mensal",
    "holerite",
    "parcelamento_fiscal",
    "prolabore_mensal",
    "provisao_mensal",
    "relatorio_gerado",
)


def upgrade() -> None:
    for tabela in _TABELAS:
        op.alter_column(
            tabela,
            "algoritmo_versao",
            existing_type=sa.String(20),
            type_=sa.String(50),
            existing_nullable=None,
        )


def downgrade() -> None:
    for tabela in _TABELAS:
        op.alter_column(
            tabela,
            "algoritmo_versao",
            existing_type=sa.String(50),
            type_=sa.String(20),
            existing_nullable=None,
        )
