"""PII em repouso -- cifra empresa.whatsapp_phone com AES-256-GCM (Marco 3).

Revision ID: 0063
Revises: 0062
Create Date: 2026-06-22

Coluna de PROVA do envelope AES-256-GCM (LGPD principio 8.7). Amplia
``empresa.whatsapp_phone`` de ``String(20)`` para ``Text`` (o ciphertext base64
nao cabe em 20 chars) e CIFRA os valores existentes (backfill). A leitura e a
escrita voltam a ser transparentes via o ``PiiCifrada`` TypeDecorator no model.

Backfill em Python (a cifra e app-level): le os telefones em texto puro e
regrava o token cifrado com ``settings.PII_ENCRYPTION_KEY`` (KMS em prod).

Em DEV/CI roda como uma migration unica (stop-the-world): apos ela, todo valor
da coluna esta cifrado e o app le/escreve via PiiCifrada -- sem janela de
inconsistencia (model + schema sobem juntos). Para deploy ZERO-DOWNTIME em prod,
dividir em 2 fases (coluna nova cifrada + dual-write -> dropar a antiga).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.config import get_settings
from app.shared.crypto.envelope import carregar_chave, cifrar, decifrar

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | None = None
depends_on: str | None = None

_SELECT = "SELECT id, whatsapp_phone FROM empresa WHERE whatsapp_phone IS NOT NULL"
_UPDATE = "UPDATE empresa SET whatsapp_phone = :v WHERE id = :id"


def upgrade() -> None:
    # Ciphertext base64 nao cabe em String(20) -> amplia ANTES do backfill.
    op.alter_column(
        "empresa", "whatsapp_phone",
        existing_type=sa.String(20), type_=sa.Text(), existing_nullable=True,
    )
    chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
    bind = op.get_bind()
    for row in bind.execute(sa.text(_SELECT)).fetchall():
        bind.execute(
            sa.text(_UPDATE),
            {"v": cifrar(row.whatsapp_phone, chave), "id": row.id},
        )


def downgrade() -> None:
    chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
    bind = op.get_bind()
    for row in bind.execute(sa.text(_SELECT)).fetchall():
        bind.execute(
            sa.text(_UPDATE),
            {"v": decifrar(row.whatsapp_phone, chave), "id": row.id},
        )
    op.alter_column(
        "empresa", "whatsapp_phone",
        existing_type=sa.Text(), type_=sa.String(20), existing_nullable=True,
    )
