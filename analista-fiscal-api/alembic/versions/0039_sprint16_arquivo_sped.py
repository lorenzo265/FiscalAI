"""Sprint 16 PR1 — Tabela ``arquivo_sped`` (SPED ECD/ECF/EFD).

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-25

Snapshot imutável de cada arquivo SPED gerado (ECD anual, ECF anual,
EFD-Contribuições mensal, EFD ICMS-IPI mensal). Re-geração para o
mesmo `(empresa, tipo, periodo_inicio, periodo_fim)` cria nova linha
com ``supersedes`` apontando para a anterior e marca a anterior com
``superseded_by`` — §8.2 (fatos imutáveis) cravado.

Conteúdo do `.txt` SPED em ``conteudo_bytea`` (BYTEA). Limite prático
do Postgres é ~1GB por valor; SPED de PME fica em 5-50MB, OK por
enquanto. ``storage_key`` fica nullable para migração futura para
S3/GCS (pendência consciente — sprint dedicada).

``hash_arquivo`` SHA-256 do conteúdo, persistido para validação de
integridade pós-download (cliente compara antes de transmitir).

``validacao_jsonb`` populado pelo validador local (PR3 desta sprint).

Princípios cravados (DB):

  * §8.1 — RLS multi-tenant.
  * §8.2 — snapshot imutável via ``supersedes`` + ``superseded_by``
    + REVOKE UPDATE/DELETE FROM PUBLIC.
  * §8.9 — UNIQUE parcial ``(empresa, tipo, periodo_inicio, periodo_fim)``
    WHERE ``superseded_by IS NULL`` impede 2 arquivos ativos para a
    mesma chave de domínio.
  * §8.12 — transmissão é ato consciente do cliente. ``status`` começa
    em ``gerado`` e o sistema NUNCA salta para ``transmitido`` por
    conta própria — a transição é registrada quando o cliente entrega
    o recibo ReceitaNet.

CHECKs:

  * ``tipo`` ∈ {ecd, ecf, efd_contribuicoes, efd_icms_ipi}
  * ``status`` ∈ {gerado, validado, transmitido, aceito, rejeitado}
  * ``periodo_fim >= periodo_inicio``
  * ``hash_arquivo ~ '^[0-9a-f]{64}$'`` (SHA-256 hex lowercase)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "arquivo_sped",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("periodo_inicio", sa.Date(), nullable=False),
        sa.Column("periodo_fim", sa.Date(), nullable=False),
        sa.Column("conteudo_bytea", sa.LargeBinary(), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("hash_arquivo", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column(
            "recibo_transmissao", sa.String(100), nullable=True,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="gerado"
        ),
        sa.Column(
            "validacao_jsonb", sa.dialects.postgresql.JSONB(), nullable=True,
        ),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column(
            "gerado_por_usuario_id", sa.UUID(), nullable=True,
        ),
        sa.Column(
            "supersedes", sa.UUID(),
            sa.ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "superseded_by", sa.UUID(),
            sa.ForeignKey("arquivo_sped.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "gerado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "transmitido_em", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "tipo IN ('ecd','ecf','efd_contribuicoes','efd_icms_ipi')",
            name="ck_sped_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('gerado','validado','transmitido','aceito','rejeitado')",
            name="ck_sped_status",
        ),
        sa.CheckConstraint(
            "periodo_fim >= periodo_inicio",
            name="ck_sped_periodo_coerente",
        ),
        sa.CheckConstraint(
            "tamanho_bytes > 0",
            name="ck_sped_tamanho_positivo",
        ),
        sa.CheckConstraint(
            "hash_arquivo ~ '^[0-9a-f]{64}$'",
            name="ck_sped_hash_formato",
        ),
    )
    op.create_index("ix_sped_tenant", "arquivo_sped", ["tenant_id"])
    op.create_index(
        "ix_sped_empresa_tipo_periodo", "arquivo_sped",
        ["empresa_id", "tipo", "periodo_inicio"],
    )
    # UNIQUE parcial — 1 arquivo ativo por chave de domínio.
    op.create_index(
        "uq_sped_ativo", "arquivo_sped",
        ["empresa_id", "tipo", "periodo_inicio", "periodo_fim"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute("ALTER TABLE arquivo_sped ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY arquivo_sped_tenant ON arquivo_sped "
        f"USING ({_RLS_USING})"
    )
    # §8.2 — fato imutável; UPDATE/DELETE só via role privilegiado (admin).
    op.execute("REVOKE UPDATE, DELETE ON arquivo_sped FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS arquivo_sped_tenant ON arquivo_sped")
    op.drop_table("arquivo_sped")
