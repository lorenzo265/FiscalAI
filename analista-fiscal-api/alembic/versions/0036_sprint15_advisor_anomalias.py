"""Sprint 15 PR1 — Tabela ``anomalia_fiscal`` (advisor proativo).

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-24

Bounded context do AI Advisor (Sprint 15). Detecta saltos atípicos em
apurações fiscais mensais (PIS, Cofins, ICMS, ISS, DAS, IRPJ, CSLL) e
gera linhas de alerta. Append-only — re-detecção da mesma chave produz
nova linha com ``superseded_by`` apontando para a anterior (§8.2).

Modelo:

  * 1 linha "ativa" por (empresa, tipo, competencia) — UNIQUE parcial
    onde ``superseded_by IS NULL`` (Princípio §8.9 — idempotência).
  * Recálculo do worker diário usa o UNIQUE para no-op quando o último
    valor não mudou; quando muda, insere nova linha + UPDATE marcando a
    anterior como superada.
  * Dispensa é UPDATE in-place (``dispensada_em`` + ``dispensada_por``) —
    a linha continua "ativa" do ponto de vista de versão (superseded_by
    IS NULL), apenas filtrada nos endpoints "abertas".

CHECKs:

  * ``tipo`` ∈ {das, irpj, csll, pis, cofins, iss, icms}
  * ``severidade`` ∈ {baixa, media, alta}
  * ``valor_observado >= 0`` e ``valor_esperado >= 0``
  * ``dispensada_em IS NULL`` ↔ ``dispensada_por IS NULL`` (coerência)

Princípios: §8.1 (RLS), §8.2 (imutável via supersedes), §8.4 (algoritmo
puro versionado), §8.9 (UNIQUE parcial), §8.10 (algoritmo_versao
persistido para auditoria).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "anomalia_fiscal",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("severidade", sa.String(10), nullable=False),
        sa.Column("valor_observado", sa.Numeric(14, 2), nullable=False),
        sa.Column("valor_esperado", sa.Numeric(14, 2), nullable=False),
        sa.Column("z_score", sa.Numeric(6, 3), nullable=False),
        sa.Column("delta_percentual", sa.Numeric(7, 4), nullable=False),
        sa.Column("metodo", sa.String(20), nullable=False),
        sa.Column("amostra_n", sa.Integer(), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column(
            "detectado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("dispensada_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dispensada_por", sa.UUID(), nullable=True),
        sa.Column("motivo_dispensa", sa.Text(), nullable=True),
        sa.Column(
            "superseded_by", sa.UUID(),
            sa.ForeignKey("anomalia_fiscal.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "tipo IN ('das','irpj','csll','pis','cofins','iss','icms')",
            name="ck_anomalia_tipo",
        ),
        sa.CheckConstraint(
            "severidade IN ('baixa','media','alta')",
            name="ck_anomalia_severidade",
        ),
        sa.CheckConstraint(
            "metodo IN ('zscore','iqr')",
            name="ck_anomalia_metodo",
        ),
        sa.CheckConstraint(
            "valor_observado >= 0 AND valor_esperado >= 0",
            name="ck_anomalia_valores_positivos",
        ),
        sa.CheckConstraint(
            "amostra_n >= 3",
            name="ck_anomalia_amostra_minima",
        ),
        sa.CheckConstraint(
            "(dispensada_em IS NULL AND dispensada_por IS NULL)"
            " OR (dispensada_em IS NOT NULL AND dispensada_por IS NOT NULL)",
            name="ck_anomalia_dispensa_coerente",
        ),
    )
    op.create_index("ix_anomalia_tenant", "anomalia_fiscal", ["tenant_id"])
    op.create_index(
        "ix_anomalia_empresa_aberta", "anomalia_fiscal",
        ["empresa_id", "detectado_em"],
        postgresql_where=sa.text(
            "superseded_by IS NULL AND dispensada_em IS NULL"
        ),
    )
    # UNIQUE parcial: apenas 1 versão ativa por (empresa, tipo, competencia).
    op.create_index(
        "uq_anomalia_ativa", "anomalia_fiscal",
        ["empresa_id", "tipo", "competencia"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute("ALTER TABLE anomalia_fiscal ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY anomalia_fiscal_tenant ON anomalia_fiscal "
        f"USING ({_RLS_USING})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS anomalia_fiscal_tenant ON anomalia_fiscal")
    op.drop_table("anomalia_fiscal")
