"""Sprint 19.6 PR1 — CIAP: ICMS de aquisição no bem imobilizado.

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-27

Pré-requisito da pendência #31: gerar Bloco G (CIAP) da EFD ICMS-IPI
exige conhecer o valor de **ICMS destacado** na NF-e de aquisição de
cada bem imobilizado. Hoje ``bem_imobilizado.valor_aquisicao`` traz o
valor cheio (com ICMS embutido) — não dá pra apurar 1/48 sem o ICMS
separado.

Adiciona coluna ``icms_aquisicao_destacado NUMERIC(14,2)`` **nullable**:

  * NULL = bem não entra no CIAP (cadastro legado sem o dado, ou
    aquisição sem ICMS destacado — operações isentas/imunes).
  * Valor preenchido = bem entra no CIAP. ICMS / 48 = parcela mensal
    apropriada por 48 meses a partir do mês da aquisição (Lei
    Complementar 87/1996 art. 20 §5º, com redação da LC 102/2000).

**Backward-compat:** ADD COLUMN nullable, sem default. Cadastros
existentes ficam com NULL — não entram no CIAP até serem preenchidos
(comportamento esperado: sem dado, não inventamos crédito).

**Princípios cravados:**

  * §8.2 — sem UPDATE em registros antigos. Linhas existentes mantêm
    histórico intacto; admin preenche o campo bem a bem.
  * §8.6 — re-check determinístico: CHECK garante valor positivo
    quando preenchido. Lógica ``calcular_apropriacao_ciap`` valida
    consistência com ``valor_aquisicao`` (ICMS não pode ser maior).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "bem_imobilizado",
        sa.Column(
            "icms_aquisicao_destacado",
            sa.Numeric(14, 2),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_bem_icms_aquisicao_positivo",
        "bem_imobilizado",
        "icms_aquisicao_destacado IS NULL OR "
        "(icms_aquisicao_destacado > 0 "
        " AND icms_aquisicao_destacado <= valor_aquisicao)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_bem_icms_aquisicao_positivo", "bem_imobilizado", type_="check"
    )
    op.drop_column("bem_imobilizado", "icms_aquisicao_destacado")
