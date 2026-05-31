"""Sprint 19.7 PR1 — IRRF Funcionários a Recolher em empresas existentes.

Revision ID: 0050
Revises: 0049
Create Date: 2026-05-29

Pendência #10: lançamento contábil automático da folha. O motor agora
exige `irrf_funcionarios_recolher` (código 2.1.3.03) no plano de contas
das empresas — sem ela, `LancadorService.resolver_contas` levanta
`PlanoContasIncompleto` e bloqueia TODOS os lotes (não só o lote de
folha).

Esta migration faz backfill **idempotente** da conta 2.1.3.03 em todas
as empresas que já têm a conta pai 2.1.3 (Encargos a Recolher) clonada.
Novas empresas que clonam o plano referencial via
`ContabilService.clonar_plano_referencial` recebem a conta automatica-
mente (já está no `plano_referencial.py` desta sprint).

**Pre-check defensivo:** o INSERT roda só para empresas onde a pai 2.1.3
existe **e** 2.1.3.03 ainda não existe (`NOT EXISTS`). Re-execução é
no-op (idempotência §8.9).

**Princípios cravados:**

  * §8.3 — conta nova entra com `valid_from = empresa.valid_from da pai`
    (mesmo período da pai, sem gap SCD).
  * §8.6 — CHECK pré-existente em `aceita_lancamento` continua valendo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Insere a conta 2.1.3.03 em toda empresa que já tem a pai 2.1.3
    # clonada. Pega `tenant_id`, `parent_id` e `valid_from` da pai —
    # garante consistência com plano clonado anteriormente.
    op.execute(
        sa.text(
            """
            INSERT INTO conta_contabil (
                id, tenant_id, empresa_id, codigo, descricao, parent_id,
                natureza, tipo, nivel, aceita_lancamento,
                codigo_ecd_referencial, valid_from, valid_to
            )
            SELECT
                gen_random_uuid(),
                pai.tenant_id,
                pai.empresa_id,
                '2.1.3.03',
                'IRRF Funcionários a Recolher',
                pai.id,
                'C',
                'passivo',
                4,
                TRUE,
                '2.01.03.03.01.01',
                pai.valid_from,
                NULL
            FROM conta_contabil pai
            WHERE pai.codigo = '2.1.3'
              AND pai.valid_to IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM conta_contabil filha
                  WHERE filha.empresa_id = pai.empresa_id
                    AND filha.codigo = '2.1.3.03'
              )
            """
        )
    )


def downgrade() -> None:
    # Remove apenas as contas 2.1.3.03 sem partidas (idempotente em
    # rollback de sistema sem lançamentos). FK ON DELETE RESTRICT em
    # partida_lancamento → conta_contabil impede remoção quando há
    # lançamentos — operador trataria caso a caso.
    op.execute(
        sa.text(
            """
            DELETE FROM conta_contabil
            WHERE codigo = '2.1.3.03'
              AND descricao = 'IRRF Funcionários a Recolher'
              AND NOT EXISTS (
                  SELECT 1 FROM partida_lancamento p
                  WHERE p.conta_contabil_id = conta_contabil.id
              )
            """
        )
    )
