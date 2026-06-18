"""INSS 2026 — nova vigência SCD (Portaria Interministerial MPS/MF nº 13/2026).

Revision ID: 0058
Revises: 0057
Create Date: 2026-06-10

Fecha PARCIALMENTE a pendência #9 do `log_agente.md` (apenas o INSS).
O seed vigente era 2025 (migration 0016, Portaria MPS/MF 6/2025) com
``valid_from=2025-01-01, valid_to=NULL``. Em 2026 a tabela foi reajustada
pelo salário mínimo (R$ 1.621,00) e novo teto (R$ 8.475,55).

Fonte oficial (primária, citável):
  PORTARIA INTERMINISTERIAL MPS/MF Nº 13, de 09/01/2026 — reajusta os
  salários de contribuição do RGPS a partir da competência janeiro/2026.
  Confirmada na página oficial gov.br/INSS — "Tabela de contribuição
  mensal" ("TABELAS VÁLIDAS A PARTIR DA COMPETÊNCIA JANEIRO DE 2026"):
  https://www.gov.br/inss/pt-br/direitos-e-deveres/inscricao-e-contribuicao/tabela-de-contribuicao-mensal

Tabela INSS empregado 2026 (alíquota progressiva escalonada):
  faixa 1 — até R$ 1.621,00  → 7,5%
  faixa 2 — até R$ 2.902,84  → 9,0%
  faixa 3 — até R$ 4.354,27  → 12,0%
  faixa 4 — até R$ 8.475,55  → 14,0% (teto = salário de contribuição máximo)

Contribuinte individual (sócio/autônomo): 11% até o teto (Lei 8.212/1991
art. 21 + teto reajustado pela mesma Portaria 13/2026).

Mecanismo SCD (§8.3):
  * INSERT de nova vigência com ``valid_from='2026-01-01', valid_to=NULL``.
  * O trigger ``scd_close_previous_valid_to`` (migration 0025) fecha o
    ``valid_to`` das vigências 2025 abertas (mesma chave (tipo, faixa),
    ``valid_from < 2026-01-01``) para ``2025-12-31`` automaticamente.
    NUNCA fazemos UPDATE/DELETE manual em linha seedada — o DB tem
    ``REVOKE UPDATE, DELETE FROM PUBLIC`` nessas tabelas.

Princípios cravados: §8.3 (SCD Type 2, sem overwrite — histórico 2024/2025
preservado), §8.4 (golden test com valores oficiais bloqueando regressão).

Escopo: SOMENTE INSS. IRRF 2026 NÃO entra aqui — a Lei 15.270/2025
introduziu redutor mensal na retenção (faixa R$ 5.000–7.350) que o schema
``tabela_irrf_faixa`` + ``calcula_irrf.py`` não modelam; exige decisão de
escopo humana (ver pendência tabelas-2026-oficiais). FGTS permanece 8%
(Lei 8.036/1990) — sem mudança legal em 2026, nenhuma vigência nova.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | None = None
depends_on: str | None = None


_FONTE_2026 = "Portaria Interministerial MPS/MF nº 13 de 09/01/2026"
_FONTE_CI_2026 = "Lei 8.212/1991 art. 21 + " + _FONTE_2026


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
    # valid_to=None: o trigger scd_close_previous_valid_to fecha a vigência
    # 2025 anterior (mesma chave tipo+faixa) em 2025-12-31. Não tocamos nela.
    op.bulk_insert(
        inss_t,
        [
            # ── INSS empregado 2026 (Portaria MPS/MF 13/2026) ──────────────
            {
                "tipo": "empregado", "faixa": 1,
                "valor_ate": "1621.00", "aliquota": "0.0750",
                "valid_from": "2026-01-01", "valid_to": None, "fonte": _FONTE_2026,
            },
            {
                "tipo": "empregado", "faixa": 2,
                "valor_ate": "2902.84", "aliquota": "0.0900",
                "valid_from": "2026-01-01", "valid_to": None, "fonte": _FONTE_2026,
            },
            {
                "tipo": "empregado", "faixa": 3,
                "valor_ate": "4354.27", "aliquota": "0.1200",
                "valid_from": "2026-01-01", "valid_to": None, "fonte": _FONTE_2026,
            },
            {
                "tipo": "empregado", "faixa": 4,
                "valor_ate": "8475.55", "aliquota": "0.1400",
                "valid_from": "2026-01-01", "valid_to": None, "fonte": _FONTE_2026,
            },
            # ── Contribuinte individual 2026 — 11% até o teto RGPS ─────────
            {
                "tipo": "contribuinte_individual", "faixa": 1,
                "valor_ate": "8475.55", "aliquota": "0.1100",
                "valid_from": "2026-01-01", "valid_to": None, "fonte": _FONTE_CI_2026,
            },
        ],
    )


def downgrade() -> None:
    # Remove as 5 linhas 2026 seedadas. O downgrade NÃO reabre as linhas 2025
    # (fechadas pelo trigger no upgrade) — reverter o valid_to=2025-12-31 para
    # NULL exigiria UPDATE em linha seedada (proibido §8.3 / REVOKE). Em prod o
    # caminho normal é forward-only; este DELETE serve só para DB scratch/CI.
    op.execute(
        "DELETE FROM tabela_inss_faixa "
        "WHERE valid_from = DATE '2026-01-01' "
        "  AND fonte LIKE 'Portaria Interministerial MPS/MF nº 13 de 09/01/2026%'"
    )
    op.execute(
        "DELETE FROM tabela_inss_faixa "
        "WHERE valid_from = DATE '2026-01-01' "
        "  AND fonte LIKE 'Lei 8.212/1991 art. 21 + Portaria Interministerial MPS/MF nº 13%'"
    )
