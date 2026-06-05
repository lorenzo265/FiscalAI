"""FA4 — Higiene SCD CBS/IBS: fechar valid_to das vigências de transição (M7).

Revision ID: 0054
Revises: 0053
Create Date: 2026-06-04

Problema (M7):
  A migration 0034 inseriu as 3 vigências de ``aliquota_cbs_ibs`` com
  ``valid_to = NULL`` em todas. O trigger ``scd_close_previous_valid_to``
  tem chave ``(fase, regime, cnae_pattern, classificacao_lc214)``; como cada
  linha tem ``fase`` distinta (``teste_2026``, ``transicao_2027_2032``,
  ``regime_pleno_2033``), o trigger NUNCA consegue fechar o ``valid_to``
  anterior — ele só fecha a vigência mais recente com a MESMA chave.

  Resultado: três intervalos ``[…, ∞)`` sobrepostos. Não quebra hoje porque
  ``repo.py._resolver_db`` filtra por ``fase`` derivada da data antes de
  consultar (lógica de higiene no código, não na tabela). Mas qualquer outro
  consumidor que consulte a tabela diretamente por data — sem replicar esse
  filtro — obteria múltiplas linhas vigentes para uma mesma competência.

Solução escolhida — fechamento explícito por seed (não alterar o trigger):

  As 3 fases são estáticas e conhecidas (cronograma LC 214/2025 é definitivo).
  Alterar o trigger seria arriscado pois ele é compartilhado com outras tabelas
  SCD (``aliquota_icms_uf``, ``presuncao_lucro_presumido`` etc.) — a chave
  ``(fase, ...)`` é por design naquelas tabelas, não um bug. A abordagem mais
  segura é fechar os ``valid_to`` via UPDATE de dado, deixando o trigger intacto
  e documentando claramente por que ele não atua aqui.

  AVISO: o UPDATE de ``valid_to`` é permitido em tabelas tributárias
  (``REVOKE UPDATE`` da migration 0034 só bloqueia PUBLIC; o superuser/alembic
  mantém permissão). Não viola §8.3 pois não altera ``valid_from`` nem as
  alíquotas — apenas sela a janela de tempo de vigências já passadas.

Janelas resultantes (sem overlap, sem gap):

  ┌──────────────────────────┬─────────────┬─────────────┐
  │ Fase                     │ valid_from  │ valid_to    │
  ├──────────────────────────┼─────────────┼─────────────┤
  │ teste_2026               │ 2026-01-01  │ 2026-12-31  │
  │ transicao_2027_2032      │ 2027-01-01  │ 2032-12-31  │
  │ regime_pleno_2033        │ 2033-01-01  │ NULL (∞)    │
  └──────────────────────────┴─────────────┴─────────────┘

  Cobertura contínua: 2026-01-01 → ∞, sem overlap, sem gap entre fases.

Princípios:
  * §8.3 (SCD Type 2): válido_from + alíquotas preservados; só ``valid_to``
    atualizado para selar vigências encerradas.
  * Migration backward-compatible (não recria tabela, não mexe em RLS).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | None = None
depends_on: str | None = None

# Tabela auxiliar para os UPDATEs — sem ORM (migration de dado puro).
_TABELA = sa.table(
    "aliquota_cbs_ibs",
    sa.column("fase", sa.String),
    sa.column("valid_to", sa.Date),
    sa.column("valid_from", sa.Date),
    sa.column("regime", sa.String),
    sa.column("cnae_pattern", sa.String),
    sa.column("classificacao_lc214", sa.String),
)


def upgrade() -> None:
    """Fecha valid_to das duas vigências encerradas do seed 0034.

    ``regime_pleno_2033`` permanece com valid_to = NULL (vigência aberta,
    pois 2033+ é o regime definitivo sem data de término conhecida).

    Os UPDATEs são idempotentes: WHERE valid_to IS NULL garante que rodar
    novamente não produz efeito colateral.

    Nota sobre o trigger scd_close_previous_valid_to:
      O trigger NÃO dispara aqui — estes são UPDATEs, não INSERTs. O trigger
      só atua em INSERT. O fechamento explícito por SQL é necessário justamente
      porque o trigger não consegue fechar vigências de fases distintas (cada
      fase é uma chave separada no índice SCD; o trigger só fecha a vigência
      anterior dentro da MESMA chave).
    """
    # ── teste_2026: encerrada em 31/12/2026 ───────────────────────────────────
    op.execute(
        sa.update(_TABELA)
        .where(_TABELA.c.fase == "teste_2026")
        .where(_TABELA.c.regime.is_(None))
        .where(_TABELA.c.cnae_pattern.is_(None))
        .where(_TABELA.c.classificacao_lc214.is_(None))
        .where(_TABELA.c.valid_from == sa.literal("2026-01-01", type_=sa.Date()))
        .where(_TABELA.c.valid_to.is_(None))
        .values(valid_to=sa.literal("2026-12-31", type_=sa.Date()))
    )

    # ── transicao_2027_2032: encerrada em 31/12/2032 ─────────────────────────
    op.execute(
        sa.update(_TABELA)
        .where(_TABELA.c.fase == "transicao_2027_2032")
        .where(_TABELA.c.regime.is_(None))
        .where(_TABELA.c.cnae_pattern.is_(None))
        .where(_TABELA.c.classificacao_lc214.is_(None))
        .where(_TABELA.c.valid_from == sa.literal("2027-01-01", type_=sa.Date()))
        .where(_TABELA.c.valid_to.is_(None))
        .values(valid_to=sa.literal("2032-12-31", type_=sa.Date()))
    )

    # ── regime_pleno_2033: valid_to permanece NULL (vigência aberta) ──────────
    # Nenhuma ação — 2033+ não tem data de término definida pela LC 214/2025.


def downgrade() -> None:
    """Reverte valid_to para NULL nas duas vigências fechadas.

    Restaura o estado do seed 0034 (todos com valid_to = NULL).
    """
    # ── desfazer fechamento de teste_2026 ─────────────────────────────────────
    op.execute(
        sa.update(_TABELA)
        .where(_TABELA.c.fase == "teste_2026")
        .where(_TABELA.c.regime.is_(None))
        .where(_TABELA.c.cnae_pattern.is_(None))
        .where(_TABELA.c.classificacao_lc214.is_(None))
        .where(_TABELA.c.valid_from == sa.literal("2026-01-01", type_=sa.Date()))
        .where(_TABELA.c.valid_to == sa.literal("2026-12-31", type_=sa.Date()))
        .values(valid_to=None)
    )

    # ── desfazer fechamento de transicao_2027_2032 ────────────────────────────
    op.execute(
        sa.update(_TABELA)
        .where(_TABELA.c.fase == "transicao_2027_2032")
        .where(_TABELA.c.regime.is_(None))
        .where(_TABELA.c.cnae_pattern.is_(None))
        .where(_TABELA.c.classificacao_lc214.is_(None))
        .where(_TABELA.c.valid_from == sa.literal("2027-01-01", type_=sa.Date()))
        .where(_TABELA.c.valid_to == sa.literal("2032-12-31", type_=sa.Date()))
        .values(valid_to=None)
    )
