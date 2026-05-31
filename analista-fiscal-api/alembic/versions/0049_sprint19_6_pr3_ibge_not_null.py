"""Sprint 19.6 PR3 — empresa.codigo_municipio_ibge NOT NULL (fase 2 do 2-fases).

Revision ID: 0049
Revises: 0048
Create Date: 2026-05-27

Pendência #17 do `log_agente.md`: Fase 2 PR6 (migration 0027) adicionou
a coluna ``codigo_municipio_ibge`` em 2-fases — fase 1 (nullable) já
foi aplicada. Esta migration é a **fase 2** (NOT NULL).

**Pré-condição obrigatória:** todas as empresas no DB têm IBGE
preenchido. Guard SQL faz pre-check antes do ALTER — se houver
``codigo_municipio_ibge IS NULL``, levanta com lista das empresas
afetadas. Em dev/test/staging com seed limpo, deve passar direto.
Em prod o operador precisa rodar backfill manual antes:

```sql
-- Para cada empresa com IBGE NULL, consultar BrasilAPI /municipios
-- e atualizar:
UPDATE empresa SET codigo_municipio_ibge = '3550308'
WHERE id = '<uuid>' AND codigo_municipio_ibge IS NULL;
```

**Após esta migration:** services não precisam mais checar `is None`
em runtime — schema impede entrada nula. ``MunicipioIbgeAusente``
continua sendo levantada se admin tentar gravar string vazia (CHECK
regex `^\\d{7}$` já bloqueia).

**Princípio §8.6:** CHECK no banco > validação só em Python.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1) Pre-check — falha se houver NULL (operador precisa backfillar primeiro).
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM empresa "
            "WHERE codigo_municipio_ibge IS NULL"
        )
    )
    n_null = result.scalar() or 0
    if n_null > 0:
        raise RuntimeError(
            f"Migration 0049 abortada: {n_null} empresa(s) com "
            f"codigo_municipio_ibge=NULL. Backfill manual obrigatório antes "
            f"do ALTER NOT NULL. Veja docstring da migration para SQL guide."
        )

    # 2) ALTER COLUMN SET NOT NULL.
    op.alter_column(
        "empresa",
        "codigo_municipio_ibge",
        existing_type=sa.String(7),
        nullable=False,
    )


def downgrade() -> None:
    # Reverte para NULL permitido (não restaura linhas).
    op.alter_column(
        "empresa",
        "codigo_municipio_ibge",
        existing_type=sa.String(7),
        nullable=True,
    )
