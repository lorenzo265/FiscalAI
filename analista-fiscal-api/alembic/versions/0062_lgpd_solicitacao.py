"""LGPD -- audit trail de solicitacoes do titular (Marco 3, direito do titular).

Revision ID: 0062
Revises: 0061
Create Date: 2026-06-22

Cria a tabela ``lgpd_solicitacao`` -- trilha de auditoria de TODA solicitacao
de direito do titular (LGPD art. 18): exportacao (portabilidade) e exclusao
(esquecimento por anonimizacao). RLS multi-tenant (USING + WITH CHECK).

  * ``tipo`` -- 'exportacao' | 'exclusao'.
  * ``status`` -- 'concluida' (ato imediato) | 'agendada' (expurgo apos
    retencao legal de 5 anos) | 'erro'.
  * ``detalhes`` -- JSONB com o resumo do que foi feito (contagens por
    entidade, campos anonimizados, etc.). NUNCA guarda a PII em si.

ENABLE (NAO FORCE) ROW LEVEL SECURITY -- mesmo padrao das tabelas de dominio:
os endpoints autenticados (``get_session``: SET ROLE fiscal_app + app.tenant_id)
respeitam a policy; nao ha webhook escrevendo aqui.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | None = None
depends_on: str | None = None

_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"


def upgrade() -> None:
    op.create_table(
        "lgpd_solicitacao",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="concluida"),
        sa.Column(
            "detalhes", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('exportacao','exclusao')",
            name="ck_lgpd_solicitacao_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('concluida','agendada','erro')",
            name="ck_lgpd_solicitacao_status",
        ),
    )
    op.create_index(
        "ix_lgpd_solicitacao_tenant", "lgpd_solicitacao", ["tenant_id"]
    )
    op.execute("ALTER TABLE lgpd_solicitacao ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY lgpd_solicitacao_tenant ON lgpd_solicitacao "
        f"USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})"
    )

    # GRANT explicito ao role das sessoes autenticadas (SET LOCAL ROLE
    # fiscal_app). O ALTER DEFAULT PRIVILEGES do init.sql NAO cobre tabelas
    # criadas via alembic -- mesmo cuidado da 0061.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON lgpd_solicitacao TO fiscal_app"
    )

    # Correcao de gap pre-existente surfado pelo export LGPD: ``guia_pagamento``
    # (criada na Sprint 2) tem RLS mas ficou SEM nenhum GRANT a fiscal_app --
    # ACL vazia. O modulo lucro_presumido acessa guias sob get_session
    # (= fiscal_app), entao o fluxo de DARF estava LATENTEMENTE quebrado (nenhum
    # teste de integracao cobria essa leitura sob o role). Alinha a tabela ao
    # padrao das demais de dominio. NAO revertido no downgrade (e correcao, nao
    # parte do feature LGPD).
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON guia_pagamento TO fiscal_app"
    )


def downgrade() -> None:
    op.drop_table("lgpd_solicitacao")
