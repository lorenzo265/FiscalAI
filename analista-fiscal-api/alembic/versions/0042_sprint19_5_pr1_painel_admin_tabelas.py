"""Sprint 19.5 PR1 — Painel admin de tabelas tributárias (vigencia_tabela_log).

Revision ID: 0042
Revises: 0041
Create Date: 2026-05-27

Substitui o anti-padrão atual de "criar migration nova toda vez que sai Portaria"
por endpoint admin (``POST /v1/admin/tabelas/<tipo>/vigencia``) que aceita JSON
estruturado da norma publicada e dispara o INSERT na tabela SCD correspondente.

Esta migration cria a **trilha de auditoria** desses POSTs:

  * ``vigencia_tabela_log`` — append-only, cross-tenant (sem RLS), uma linha
    por POST aceito. Guarda o snapshot completo do payload (JSONB), a
    citação da norma (``fonte_norma`` ≥ 10 chars validado em §8.5), o
    autor (``usuario_admin_id``) e a ``idempotency_key`` (UUID5 §8.9) que
    permite re-POST idempotente.

Os ``INSERT``s nas tabelas SCD tributárias propriamente ditas (``tabela_inss_faixa``,
``tabela_irrf_faixa``, ``tabela_fgts_aliquota``, ``tabela_simples_faixa``,
``presuncao_lucro_presumido``, ``aliquota_icms_uf``, ``aliquota_cbs_ibs``) acionam
o trigger ``scd_close_previous_valid_to`` da migration 0025, que fecha o ``valid_to``
da vigência anterior automaticamente — esta migration **não** cria nem mexe nele.

Permissões:
  * ``GRANT INSERT, SELECT ON vigencia_tabela_log TO tax_table_admin``
    (alinha-se às SCD tributárias da 0025).
  * ``REVOKE UPDATE, DELETE ON vigencia_tabela_log FROM PUBLIC``
    (append-only — princípio §8.2 estendido para o log de auditoria).

Sem RLS: a operação é cross-tenant de sistema, controlada exclusivamente pelo
role ``tax_table_admin`` + token estático ``MARKETPLACE_ADMIN_TOKEN`` (reusa o
guard do marketplace — Sprint 13 PR1).

Princípios cravados:

  * §8.2 Fatos imutáveis — append-only via REVOKE UPDATE/DELETE.
  * §8.5 Citação obrigatória — coluna ``fonte_norma`` NOT NULL (≥ 10 chars
    validado na borda Pydantic).
  * §8.9 Idempotência — ``idempotency_key UNIQUE``; re-POST devolve log
    anterior sem reescrever (verificado no service).
  * §8.10 Observabilidade — toda escrita administrativa fica rastreada
    (autor + payload + timestamp).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | None = None
depends_on: str | None = None


_TIPOS_SUPORTADOS: tuple[str, ...] = (
    "inss",
    "irrf",
    "fgts",
    "simples_nacional",
    "presuncao_lp",
    "icms_uf",
    "cbs_ibs",
)


def upgrade() -> None:
    op.create_table(
        "vigencia_tabela_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tipo_tabela", sa.String(40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("fonte_norma", sa.Text(), nullable=False),
        sa.Column(
            "payload_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "usuario_admin_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "idempotency_key",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("registros_criados", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_tabela IN (" + ",".join(f"'{t}'" for t in _TIPOS_SUPORTADOS) + ")",
            name="ck_vig_tab_log_tipo",
        ),
        sa.CheckConstraint(
            "char_length(fonte_norma) >= 10",
            name="ck_vig_tab_log_fonte_minima",
        ),
        sa.CheckConstraint(
            "registros_criados >= 0",
            name="ck_vig_tab_log_registros_nao_negativo",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_vig_tab_log_idempotency"),
    )

    op.create_index(
        "ix_vig_tab_log_tipo_data",
        "vigencia_tabela_log",
        ["tipo_tabela", sa.text("valid_from DESC")],
    )
    op.create_index(
        "ix_vig_tab_log_criado_em",
        "vigencia_tabela_log",
        [sa.text("criado_em DESC")],
    )

    # Permissões — alinha-se com migration 0025 (SCD hardening).
    # GRANT INSERT, SELECT para o role admin.
    # REVOKE UPDATE, DELETE de PUBLIC: append-only por construção (§8.2).
    op.execute(
        "GRANT INSERT, SELECT ON vigencia_tabela_log TO tax_table_admin"
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON vigencia_tabela_log FROM PUBLIC"
    )


def downgrade() -> None:
    # Reativa UPDATE/DELETE antes de dropar (idempotência do downgrade).
    op.execute("GRANT UPDATE, DELETE ON vigencia_tabela_log TO PUBLIC")
    op.execute(
        "REVOKE INSERT, SELECT ON vigencia_tabela_log FROM tax_table_admin"
    )
    op.drop_index("ix_vig_tab_log_criado_em", table_name="vigencia_tabela_log")
    op.drop_index("ix_vig_tab_log_tipo_data", table_name="vigencia_tabela_log")
    op.drop_table("vigencia_tabela_log")
