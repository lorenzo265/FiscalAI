"""Sprint 19.6 PR1 — Seed retroativo da tabela INSS 2024.

Revision ID: 0045
Revises: 0044
Create Date: 2026-05-27

Fecha a pendência #37 do `log_agente.md`. A Sprint 10 PR1 (migration 0016)
seedou apenas a vigência INSS 2025 (Portaria MPS/MF 6/2025) com
``valid_from=2025-01-01, valid_to=NULL``. Cliente importando folha de
2024 via Sprint 18 PR2 caía em "tabela INSS ausente" no service e
recebia cálculo errado.

Esta migration insere as **5 linhas SCD vigentes em 2024**:

  * 4 faixas progressivas tipo='empregado' (Portaria Interministerial
    MPS/MF nº 2 de 11/01/2024 — DOU 12/01/2024).
  * 1 faixa tipo='contribuinte_individual' (11% até o teto do RGPS,
    art. 21 da Lei 8.212/1991 + reajuste do teto na mesma Portaria 2/2024).

Cada linha tem ``valid_from='2024-01-01'`` e ``valid_to='2024-12-31'``
explícito — fecha o ano. As linhas 2025 existentes ficam intactas
(``valid_from=2025-01-01, valid_to=NULL``), preservando histórico §8.3.

**Por que não usar painel admin (Sprint 19.5):** o painel admin
(``POST /v1/admin/tabelas/inss/vigencia``) rejeita ``valid_from`` ≤
``max(valid_from)`` existente via `_checar_idempotencia_e_max_valid_from`
em `TabelaAdminService` — anti-regressão temporal deliberada. Esta
proteção evita que um admin poste retroativo por engano; seed real
de período passado roda via SQL direto (esta migration), preservando
a UX do painel.

**Princípios cravados:**

  * §8.3 — SCD Type 2 sem overwrite. Linhas 2025 ficam ativas pra
    competências 2025+; linhas 2024 cobrem 2024-01-01..2024-12-31.
  * §8.9 — `bulk_insert` é idempotente apenas em primeira execução;
    re-execução do downgrade+upgrade duplicaria. Em prod, alembic
    bloqueia re-execução por `alembic_version`.

**Trigger SCD (migration 0025):** o trigger
``scd_close_previous_valid_to`` filtra `valid_to IS NULL AND valid_from
< NEW.valid_from`. Como esta migration insere vigências com
`valid_from=2024-01-01` (anterior a tudo), o trigger é no-op para todas
as linhas inseridas — comportamento esperado.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | None = None
depends_on: str | None = None


_FONTE_2024 = (
    "Portaria Interministerial MPS/MF nº 2 de 11/01/2024 (DOU 12/01/2024)"
)
_FONTE_CI_2024 = "Lei 8.212/1991 art. 21 + " + _FONTE_2024


def upgrade() -> None:
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
    op.bulk_insert(
        inss_t,
        [
            # ── INSS empregado 2024 (Portaria MPS/MF 2/2024) ──────────────
            {
                "tipo": "empregado",
                "faixa": 1,
                "valor_ate": "1412.00",
                "aliquota": "0.0750",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "fonte": _FONTE_2024,
            },
            {
                "tipo": "empregado",
                "faixa": 2,
                "valor_ate": "2666.68",
                "aliquota": "0.0900",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "fonte": _FONTE_2024,
            },
            {
                "tipo": "empregado",
                "faixa": 3,
                "valor_ate": "4000.03",
                "aliquota": "0.1200",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "fonte": _FONTE_2024,
            },
            {
                "tipo": "empregado",
                "faixa": 4,
                "valor_ate": "7786.02",
                "aliquota": "0.1400",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "fonte": _FONTE_2024,
            },
            # ── Contribuinte individual 2024 — 11% até teto RGPS ──────────
            {
                "tipo": "contribuinte_individual",
                "faixa": 1,
                "valor_ate": "7786.02",
                "aliquota": "0.1100",
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "fonte": _FONTE_CI_2024,
            },
        ],
    )


def downgrade() -> None:
    # Remove exatamente as 5 linhas seedadas em upgrade(). Filtro pelo
    # par (valid_from, valid_to) é seguro: nenhuma outra vigência usa
    # exatamente '2024-01-01' a '2024-12-31'.
    op.execute(
        "DELETE FROM tabela_inss_faixa "
        "WHERE valid_from = DATE '2024-01-01' "
        "  AND valid_to = DATE '2024-12-31'"
    )
