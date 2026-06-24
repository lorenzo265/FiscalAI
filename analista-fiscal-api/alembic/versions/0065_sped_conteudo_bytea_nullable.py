"""SPED: conteudo_bytea nullable (blob migra para object storage) -- Marco 4 #10.

Revision ID: 0065
Revises: 0064
Create Date: 2026-06-23

O conteudo do .txt SPED (ECD/ECF/EFD) passa a viver no object storage
(arquivo_sped.storage_key + app.state.storage), nao mais em BYTEA. A coluna
conteudo_bytea vira NULLABLE: a geracao nova grava no storage e deixa
conteudo_bytea NULL; linhas legadas mantem o BYTEA ate o backfill
(mover_blob_sped_para_storage, idempotente). A leitura e storage-first com
fallback BYTEA.

Apenas DDL (widening nullable, backward-compatible). Sem RLS/GRANT novos --
arquivo_sped ja existe (Sprint 16) com policy + grants. O downgrade reaplica
NOT NULL e SO funciona se nenhuma linha estiver storage-only (i.e. apos
backfill reverso do storage para o BYTEA, que nao e automatizavel aqui).
"""

from __future__ import annotations

from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE arquivo_sped ALTER COLUMN conteudo_bytea DROP NOT NULL")


def downgrade() -> None:
    # Reaplica NOT NULL. Falha se houver linha storage-only (conteudo_bytea
    # NULL); nesse caso restaure o BYTEA a partir do storage antes do downgrade.
    op.execute("ALTER TABLE arquivo_sped ALTER COLUMN conteudo_bytea SET NOT NULL")
