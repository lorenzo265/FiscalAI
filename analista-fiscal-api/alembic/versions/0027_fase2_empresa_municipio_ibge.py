"""Fase 2 PR6 — código IBGE 7-dígitos do município da empresa (CRITICAL C1).

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-20

Auditoria das Sprints 4-6 identificou que ``empresa.municipio`` é ``String(100)``
sem CHECK e é populado com o NOME do município (vindo de BrasilAPI ``/cnpj``).
Mas as integrações:

  * ``app/modules/notas/service.py`` envia ``empresa.municipio`` como
    ``codigo_municipio`` ao Focus NFe (esperado: código IBGE 7 dígitos);
  * ``app/modules/pgdas/service.py`` envia ``empresa.municipio`` como
    ``municipio`` ao SERPRO PGDAS-D (esperado: código IBGE 7 dígitos).

Sem o IBGE 7-dígitos, **toda emissão de NFS-e e transmissão de PGDAS** falha
com erro 400 das APIs. A migration adiciona a coluna ``codigo_municipio_ibge``
com CHECK regex ``^\\d{7}$`` (formato IBGE), nullable até backfill manual no
piloto (0 empresas em produção hoje).

Pattern 2 fases (CLAUDE.md): NOT NULL fica para migration futura após backfill
completo. Service emite ``MunicipioIbgeAusente`` (422) se for emitido NFS-e
ou transmitido PGDAS com IBGE ainda nulo — falha cedo, mensagem clara.

Princípios aplicados: §8.9 (idempotência — validação na borda) e Gate 2 da
auditoria fiscal-br (CEP/IBGE lookup obrigatório para ISS por município).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "empresa",
        sa.Column("codigo_municipio_ibge", sa.String(7), nullable=True),
    )
    op.create_check_constraint(
        "ck_empresa_municipio_ibge_formato",
        "empresa",
        "codigo_municipio_ibge IS NULL OR codigo_municipio_ibge ~ '^[0-9]{7}$'",
    )
    op.create_index(
        "ix_empresa_codigo_municipio_ibge",
        "empresa",
        ["codigo_municipio_ibge"],
    )


def downgrade() -> None:
    op.drop_index("ix_empresa_codigo_municipio_ibge", table_name="empresa")
    op.drop_constraint("ck_empresa_municipio_ibge_formato", "empresa", type_="check")
    op.drop_column("empresa", "codigo_municipio_ibge")
