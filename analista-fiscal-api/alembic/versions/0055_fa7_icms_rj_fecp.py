"""FA7-m2 — ICMS RJ: separar interna=18% e FECP=2% no seed.

Revision ID: 0055
Revises: 0054
Create Date: 2026-06-04

Problema (M2 da auditoria fiscal):
  A migration 0020 inseriu RJ com ``aliquota_interna=0.20`` e
  ``aliquota_fecp=0.02``, com comentário "18%+FECP 2%". O algoritmo
  ``calcula_icms.py`` usava ``aliquota_interna`` diretamente e ignorava
  ``aliquota_fecp`` — portanto o ICMS efetivo do RJ saía 20% (correto no
  total), mas:

  1. O dado estava mal-rotulado: ``interna=0.20`` era o TOTAL (interna+FECP),
     não a alíquota interna pura.
  2. O campo ``aliquota_fecp=0.02`` era morto (nunca lido pelo algoritmo).
  3. Risco latente de dupla contagem: qualquer consumidor que somasse
     ``interna + fecp`` obteria 22% (errado).

Solução (Opção A — FA7-m2):
  * Corrigir o seed: ``interna=0.18`` (alíquota pura RJ — sem FECP) e
    ``fecp=0.02`` (FECP — Lei estadual RJ 4.056/2002).
  * Algoritmo ``calcula_icms.py`` bumped para v2: soma ``interna + fecp``
    para obter a alíquota efetiva, expondo ambos no resultado.
  * O ICMS efetivo do RJ continua 20% (= 18% + 2%) — sem mudança fiscal.

Revisão das demais UFs:
  * Nenhuma outra UF do seed 0020 apresenta o padrão "interna inclui FECP
    E fecp > 0" simultaneamente. As UFs com FECP zero (todas exceto RJ)
    estão corretas: ``interna`` é a alíquota total e ``fecp=0``.
  * BA e PE possuem ``aliquota_fecp=0`` com ``interna`` já incluindo o
    adicional estadual — padrão diferente e correto (fecp=0 → sem campo morto).

Downgrade:
  * Restaura RJ para ``interna=0.20, fecp=0.02`` (estado do 0020).

Princípios satisfeitos:
  §8.3 — SCD: nova vigência criada por UPDATE (campo de dado, não estrutura).
  §8.1 — RLS: tabela pública (sem RLS), sem impacto.
  §8.4 — Golden tests: RJ efetivo == 20% antes e depois provado em
          ``tests/unit/icms/test_calcula_icms.py::TestFA7M2IcmsRjFecp``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Corrige seed RJ: interna 0.20 → 0.18 (FECP permanece 0.02, separado)."""
    op.execute(
        sa.text(
            """
            UPDATE aliquota_icms_uf
               SET aliquota_interna = 0.18,
                   fonte = 'CONFAZ + leis estaduais vigentes 2025 '
                           '(FA7-m2: interna 18% puro, FECP 2% separado — '
                           'Lei estadual RJ 4.056/2002)'
             WHERE uf = 'RJ'
               AND valid_from = '2025-01-01'
               AND valid_to IS NULL
            """
        )
    )


def downgrade() -> None:
    """Reverte RJ para estado do 0020: interna=0.20 (FECP embutido)."""
    op.execute(
        sa.text(
            """
            UPDATE aliquota_icms_uf
               SET aliquota_interna = 0.20,
                   fonte = 'CONFAZ + leis estaduais vigentes 2025'
             WHERE uf = 'RJ'
               AND valid_from = '2025-01-01'
               AND valid_to IS NULL
            """
        )
    )
