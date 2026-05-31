"""Sprint 19.5 PR2 — Worker Celery de alerta proativo (alerta_admin).

Revision ID: 0043
Revises: 0042
Create Date: 2026-05-27

Camada 2 do painel admin. Worker diário ``tabelas.verificar_vigencias``
varre as 7 tabelas SCD tributárias e cria alertas em ``alerta_admin`` quando
uma vigência fica desatualizada (regras por tipo no worker — ver módulo).

Tabela ``alerta_admin``:

  * Cross-tenant operacional (sem RLS). Mesma família do ``vigencia_tabela_log``
    da migration 0042 — controlada pelo role ``tax_table_admin``.
  * Idempotência §8.9: ``idempotency_key UUID UNIQUE`` derivada de
    ``uuid5(NS_TABELA_ADMIN, "alerta|{tipo}|{tipo_tabela}|{ano_corrente}")``
    — 2 runs do worker no mesmo período não criam 2 alertas.
  * Resolução: ``resolvido_em + resolvido_por_usuario_id`` (UPDATE in-place,
    diferente do ``vigencia_tabela_log`` que é puro append-only). Esta tabela
    é operacional — não é fato fiscal, então UPDATE é aceitável.
  * Snooze: ``resolvido_em`` recebe a data futura escolhida; alertas com
    ``resolvido_em > now()`` ficam invisíveis aos endpoints "abertos".

Severidades (espelhadas do CHECK):
  * ``info``    — aviso baixo (FGTS / Presunção LP > 10 anos sem atualização).
  * ``aviso``   — atenção (CGSN > 5 anos, ICMS UF > 2 anos).
  * ``critico`` — INSS/IRRF não atualizadas no ano corrente (mês ≥ março).

Princípios cravados:
  * §8.9 — idempotência via UUID UNIQUE.
  * §8.10 — log estruturado em todo INSERT/UPDATE.
  * §8.1 — sem RLS por design (admin de sistema), GRANT só p/ role admin.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | None = None
depends_on: str | None = None


_SEVERIDADES: tuple[str, ...] = ("info", "aviso", "critico")


def upgrade() -> None:
    op.create_table(
        "alerta_admin",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("severidade", sa.String(10), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column(
            "contexto_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "idempotency_key",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "resolvido_em",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolvido_por_usuario_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "criado_em",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severidade IN (" + ",".join(f"'{s}'" for s in _SEVERIDADES) + ")",
            name="ck_alerta_admin_severidade",
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_alerta_admin_idempotency"
        ),
    )

    # Aberto = resolvido_em IS NULL (ou resolvido_em > now() para snooze).
    # Index parcial para o filtro padrão dos endpoints "alertas abertos".
    op.execute(
        "CREATE INDEX ix_alerta_admin_abertos "
        "ON alerta_admin (severidade, criado_em DESC) "
        "WHERE resolvido_em IS NULL"
    )
    op.create_index(
        "ix_alerta_admin_tipo",
        "alerta_admin",
        ["tipo"],
    )

    # GRANT mais amplo que o vigencia_tabela_log: aqui o UPDATE é legítimo
    # (resolver / snooze). DELETE continua proibido para PUBLIC — manter
    # histórico de alertas é útil para post-mortem.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON alerta_admin TO tax_table_admin"
    )
    op.execute("REVOKE DELETE ON alerta_admin FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT DELETE ON alerta_admin TO PUBLIC")
    op.execute("REVOKE SELECT, INSERT, UPDATE ON alerta_admin FROM tax_table_admin")
    op.drop_index("ix_alerta_admin_tipo", table_name="alerta_admin")
    op.execute("DROP INDEX IF EXISTS ix_alerta_admin_abertos")
    op.drop_table("alerta_admin")
