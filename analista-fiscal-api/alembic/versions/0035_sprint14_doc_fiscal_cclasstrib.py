"""Sprint 14 PR2 — ``documento_fiscal.cclasstrib`` (Reforma Tributária).

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-22

Adiciona ``cclasstrib VARCHAR(20)`` em ``documento_fiscal`` para suportar o
**Código de Classificação Tributária CBS/IBS** introduzido pela NF-e 4.x na
trilha da Reforma Tributária (LC 214/2025 art. 9º + Nota Técnica 2025/001
da Receita Federal — em consolidação via Comitê Gestor IBS).

O campo é opcional (NF-e 4.0 sem extensão IBSCBS não traz; valor NULL
preservado retroativamente). CHECK regex ``^[0-9]{6}$`` aceita só o
formato canônico de 6 dígitos (ex.: ``000001`` para "regime geral").
Linhas com cclasstrib NULL são tratadas como "classificação não-informada"
pelo simulador do PR3.

Princípio §8.2: ``documento_fiscal`` é imutável — UPDATE de cclasstrib
existente fica bloqueado pela política de hardening da migration 0024
(REVOKE UPDATE FROM PUBLIC). Para correção de cclasstrib em nota
historicamente ingerida sem o campo, o caminho é via worker administrativo
com role específico (não é caminho de uso normal — campo informacional).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "documento_fiscal",
        sa.Column("cclasstrib", sa.String(20), nullable=True),
    )
    op.create_check_constraint(
        "ck_doc_cclasstrib_formato",
        "documento_fiscal",
        r"cclasstrib IS NULL OR cclasstrib ~ '^[0-9]{6}$'",
    )
    op.create_index(
        "ix_doc_cclasstrib",
        "documento_fiscal",
        ["cclasstrib"],
        postgresql_where=sa.text("cclasstrib IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_doc_cclasstrib", table_name="documento_fiscal")
    op.drop_constraint(
        "ck_doc_cclasstrib_formato", "documento_fiscal", type_="check"
    )
    op.drop_column("documento_fiscal", "cclasstrib")
