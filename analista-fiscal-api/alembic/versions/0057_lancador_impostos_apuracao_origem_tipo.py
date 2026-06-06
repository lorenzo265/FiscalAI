"""Lançador de impostos — estende ck_lanc_origem_tipo para incluir 'apuracao'.

Revision ID: 0057
Revises: 0056
Create Date: 2026-06-06

``lote_impostos`` (LancadorService) persiste lançamentos contábeis com
``origem_tipo='apuracao'`` linkando cada ``ApuracaoFiscal`` ao seu
lançamento correspondente (D 5.1.05/5.3.01 / C 2.1.4.0x). O CHECK
``ck_lanc_origem_tipo`` não incluía 'apuracao' — esta migration estende
o allowlist para destravá-lo.

Sem mudança de schema além do CHECK; backward-compatible (superset).
"""

from __future__ import annotations

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | None = None
depends_on: str | None = None

_COM_APURACAO = (
    "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
    "'provisao','encerramento','ajuste','importacao','folha','apuracao')"
)
_SEM_APURACAO = (
    "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
    "'provisao','encerramento','ajuste','importacao','folha')"
)


def upgrade() -> None:
    op.drop_constraint("ck_lanc_origem_tipo", "lancamento_contabil", type_="check")
    op.create_check_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", _COM_APURACAO
    )


def downgrade() -> None:
    op.drop_constraint("ck_lanc_origem_tipo", "lancamento_contabil", type_="check")
    op.create_check_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", _SEM_APURACAO
    )
