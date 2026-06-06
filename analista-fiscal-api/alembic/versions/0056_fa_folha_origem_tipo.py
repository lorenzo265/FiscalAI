"""Integração front-back — inclui 'folha' no CHECK ``ck_lanc_origem_tipo``.

Revision ID: 0056
Revises: 0055
Create Date: 2026-06-05

Bug encontrado na integração front↔back (tela Pessoal → fechar folha):

  ``ContabilLancadorService.lote_folha`` (Sprint 19.7 PR1 #10) cria o
  lançamento contábil automático da folha com ``origem_tipo='folha'`` e é
  idempotente por ``UNIQUE(origem_tipo='folha', origem_id=folha.id)``. Porém
  o CHECK ``ck_lanc_origem_tipo`` (criado em 0014, estendido em 0040 para
  incluir 'importacao') **nunca incluiu 'folha'** — então o INSERT do
  lançamento viola o CHECK e o fechamento da folha falhava (a folha e os
  holerites persistiam, mas o lançamento automático não, e o endpoint
  devolvia 500).

  Esta migration apenas estende o allowlist do CHECK para o valor que o
  código já usa — destrava o fluxo Pessoal → Contábil → Relatórios com dado
  real. Sem mudança de schema além do CHECK; backward-compatible.
"""

from __future__ import annotations

from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | None = None
depends_on: str | None = None

_ORIGENS_COM_FOLHA = (
    "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
    "'provisao','encerramento','ajuste','importacao','folha')"
)
_ORIGENS_SEM_FOLHA = (
    "origem_tipo IN ('manual','nfe','transacao','depreciacao',"
    "'provisao','encerramento','ajuste','importacao')"
)


def upgrade() -> None:
    op.drop_constraint("ck_lanc_origem_tipo", "lancamento_contabil", type_="check")
    op.create_check_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", _ORIGENS_COM_FOLHA
    )


def downgrade() -> None:
    op.drop_constraint("ck_lanc_origem_tipo", "lancamento_contabil", type_="check")
    op.create_check_constraint(
        "ck_lanc_origem_tipo", "lancamento_contabil", _ORIGENS_SEM_FOLHA
    )
