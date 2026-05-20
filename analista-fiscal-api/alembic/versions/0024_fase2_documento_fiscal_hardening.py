"""Fase 2 PR1 — Hardening de ``documento_fiscal`` (princípios §8.2 + §8.9).

Revision ID: 0024
Revises: 0022
Create Date: 2026-05-19

Cole o princípio invioólavel §8.2 (fatos fiscais imutáveis) e §8.9
(idempotência) ao schema do banco — eles deixam de ser prosa do Plano
e viram constraint cravada na tabela.

Mudanças (em 3 fases lógicas, idempotentes):

  Fase 1 — Estrutural
    * Adiciona ``superseded_by UUID NULL`` espelhando ``supersedes``
      (mantém o grafo bidirecional: dado um documento, descubro em
      O(1) qual o substituto vigente).
    * Index parcial ``ix_doc_vigente`` para acesso rápido aos não-supersedidos.

  Fase 2 — Backfill defensivo
    * Para cada par (antigo, novo) onde ``novo.supersedes = antigo.id``,
      seta ``antigo.superseded_by = novo.id``.
    * Normaliza dados eventualmente inválidos em ``cfop``/``cst`` para
      ``NULL`` (ex.: regex fora de ``^\\d{4}$`` / ``^\\d{2,3}$``) — apenas
      ``UPDATE`` legítimo nessa migration; depois disso a tabela é
      protegida via ``REVOKE``.
    * Normaliza ``evento`` fora do enum para ``NULL``.

  Fase 3 — Integridade
    * ``UNIQUE (empresa_id, chave) WHERE superseded_by IS NULL AND chave IS NOT NULL``
      — uma chave NF-e tem no máximo um documento vigente por empresa.
    * ``CHECK evento IN ('cancelou','denegou','retificou')`` (nullable).
    * ``CHECK cfop ~ '^\\d{4}$'`` (nullable).
    * ``CHECK cst ~ '^\\d{2,3}$'`` (nullable).
    * ``REVOKE UPDATE, DELETE ON documento_fiscal FROM PUBLIC`` —
      mutação só via role administrativa explícita (futuramente
      ``tax_audit_admin``); aplicação só faz ``INSERT`` (nova versão).

Risco mitigado: dados existentes podem violar CHECK — a Fase 2 limpa
proativamente. RLS já estava ativo (migration 0002) e é preservado.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0022"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ─── Fase 1 — Estrutural ─────────────────────────────────────────────────
    op.add_column(
        "documento_fiscal",
        sa.Column(
            "superseded_by",
            sa.UUID(),
            sa.ForeignKey("documento_fiscal.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_doc_vigente",
        "documento_fiscal",
        ["empresa_id", "tipo", "emitida_em"],
        postgresql_where=sa.text("superseded_by IS NULL"),
    )

    # ─── Fase 2 — Backfill defensivo ────────────────────────────────────────
    # Reconstroi superseded_by a partir de supersedes (inverso da relação).
    op.execute(
        """
        UPDATE documento_fiscal antigo
           SET superseded_by = novo.id
          FROM documento_fiscal novo
         WHERE novo.supersedes = antigo.id
           AND antigo.superseded_by IS NULL
        """
    )

    # Limpa CFOP fora de ^\d{4}$ → NULL (preserva o documento mas remove o lixo).
    op.execute(
        r"""
        UPDATE documento_fiscal
           SET cfop = NULL
         WHERE cfop IS NOT NULL
           AND cfop !~ '^\d{4}$'
        """
    )

    # Limpa CST fora de ^\d{2,3}$ → NULL.
    op.execute(
        r"""
        UPDATE documento_fiscal
           SET cst = NULL
         WHERE cst IS NOT NULL
           AND cst !~ '^\d{2,3}$'
        """
    )

    # Normaliza evento fora do enum → NULL.
    op.execute(
        """
        UPDATE documento_fiscal
           SET evento = NULL
         WHERE evento IS NOT NULL
           AND evento NOT IN ('cancelou','denegou','retificou')
        """
    )

    # ─── Fase 3 — Integridade ───────────────────────────────────────────────
    # UNIQUE parcial: uma chave NF-e tem no máximo um documento vigente por empresa.
    op.create_index(
        "uq_doc_empresa_chave_vigente",
        "documento_fiscal",
        ["empresa_id", "chave"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL AND chave IS NOT NULL"),
    )

    op.create_check_constraint(
        "ck_doc_evento",
        "documento_fiscal",
        "evento IS NULL OR evento IN ('cancelou','denegou','retificou')",
    )
    op.create_check_constraint(
        "ck_doc_cfop_formato",
        "documento_fiscal",
        r"cfop IS NULL OR cfop ~ '^\d{4}$'",
    )
    op.create_check_constraint(
        "ck_doc_cst_formato",
        "documento_fiscal",
        r"cst IS NULL OR cst ~ '^\d{2,3}$'",
    )

    # REVOKE UPDATE/DELETE — só INSERT é permitido. SELECT preserva-se.
    # Aplicação roda como PUBLIC; mutações futuras (caso necessárias para
    # remediação fiscal real) exigirão role tax_audit_admin (criada sob demanda).
    op.execute("REVOKE UPDATE, DELETE ON documento_fiscal FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON documento_fiscal TO PUBLIC")

    op.drop_constraint("ck_doc_cst_formato", "documento_fiscal", type_="check")
    op.drop_constraint("ck_doc_cfop_formato", "documento_fiscal", type_="check")
    op.drop_constraint("ck_doc_evento", "documento_fiscal", type_="check")

    op.drop_index("uq_doc_empresa_chave_vigente", table_name="documento_fiscal")
    op.drop_index("ix_doc_vigente", table_name="documento_fiscal")

    op.drop_column("documento_fiscal", "superseded_by")
