"""Sprint 13 PR1 — Marketplace de contadores parceiros (§5.8 / §10).

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-21

Duas tabelas + role + RLS dual:

  * ``contador_parceiro`` — pool global (SEM tenant_id), curado manualmente.
    REVOKE UPDATE,DELETE FROM PUBLIC: rating e suspensão só via role admin.
  * ``consulta_marketplace`` — RLS dual (princípio §8.1 estendido):
       1. Policy ``consulta_mkt_tenant`` — cliente da PME vê via
          ``app.tenant_id`` (mesmo padrão dos outros módulos).
       2. Policy ``consulta_mkt_parceiro`` — contador parceiro vê via
          ``app.contador_id`` (GUC separada). Aplicada à role
          ``marketplace_partner`` (sem login; acessível via SET LOCAL ROLE).
    ``FORCE ROW LEVEL SECURITY`` garante que superuser (fiscal) respeita as
    duas policies.

Princípios:
  §8.1 — RLS multi-tenant (com extensão dual para o pool global de parceiros).
  §8.2 — Append-only nos campos de identidade (pergunta_hash imutável;
         ``pii_apagado_em`` é o único UPDATE permitido sobre ``pergunta`` e
         ``contexto_empresa_jsonb`` via task LGPD de expurgo — PR3).
  §8.7 — Consentimento por consulta + revogação (campos LGPD nativos).
  §8.9 — ``idempotency_key UUID UNIQUE`` cravado em DB.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | None = None
depends_on: str | None = None

# RLS via GUCs separados: app.tenant_id (cliente PME) ou app.contador_id
# (parceiro). NULLIF + boolean OR garante que cada role só atinge sua linha
# (tenant não setado → primeira metade falsa; contador não setado → segunda
# metade falsa).
_RLS_TENANT_USING = (
    "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"
)
_RLS_PARCEIRO_USING = (
    "NULLIF(current_setting('app.contador_id', TRUE), '')::uuid = contador_id"
)


def upgrade() -> None:
    _criar_role_marketplace_partner()
    _criar_contador_parceiro()
    _criar_consulta_marketplace()


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS consulta_mkt_parceiro ON consulta_marketplace")
    op.execute("DROP POLICY IF EXISTS consulta_mkt_tenant ON consulta_marketplace")
    op.drop_table("consulta_marketplace")
    op.drop_table("contador_parceiro")
    # Role é compartilhada com migrations futuras (PR3 cria endpoints);
    # mantemos idempotente no upgrade mas removemos só se vazia no downgrade.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'marketplace_partner') THEN "
        "  REVOKE ALL ON consulta_marketplace FROM marketplace_partner; "
        "  DROP ROLE marketplace_partner; "
        "END IF; "
        "EXCEPTION WHEN dependent_objects_still_exist THEN NULL; "
        "END $$"
    )


def _criar_role_marketplace_partner() -> None:
    """Cria role NOLOGIN idempotentemente. Acessível via ``SET LOCAL ROLE``."""
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'marketplace_partner') THEN "
        "  CREATE ROLE marketplace_partner NOLOGIN; "
        "END IF; "
        "END $$"
    )


def _criar_contador_parceiro() -> None:
    op.create_table(
        "contador_parceiro",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("cnpj", sa.String(14), nullable=True),
        sa.Column("crc_numero", sa.String(20), nullable=False),
        sa.Column("crc_uf", sa.CHAR(2), nullable=False),
        sa.Column(
            "crc_status", sa.String(20), nullable=False, server_default="ativo",
        ),
        sa.Column(
            "crc_status_atualizado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        # JSONB list[str]: ex. ['tributario','trabalhista','contencioso']
        sa.Column(
            "especialidades", sa.dialects.postgresql.JSONB(), nullable=False,
        ),
        # JSONB list[str] de UFs onde atua. NULL = atuação nacional.
        sa.Column(
            "uf_atuacao", sa.dialects.postgresql.JSONB(), nullable=True,
        ),
        sa.Column("rating_medio", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "total_consultas", sa.Integer(), nullable=False, server_default="0",
        ),
        sa.Column("taxa_resposta_horas", sa.Integer(), nullable=True),
        sa.Column(
            "sla_resposta_horas", sa.Integer(), nullable=False, server_default="24",
        ),
        sa.Column("oab_numero", sa.String(20), nullable=True),
        sa.Column("oab_uf", sa.CHAR(2), nullable=True),
        # Senha hash p/ login do parceiro (auth real entra no PR3). Nullable
        # aqui porque cadastro inicial pode ser feito sem senha definida.
        sa.Column("senha_hash", sa.String(255), nullable=True),
        # NDA + termo LGPD aceito (timestamp). NULL = não aceito ainda.
        sa.Column(
            "aceitou_nda_lgpd_em", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        # ``ativo=false`` até curadoria aprovar (§10.4).
        sa.Column(
            "ativo", sa.Boolean(), nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "crc_status IN ('ativo','suspenso','baixado')",
            name="ck_contador_crc_status",
        ),
        sa.CheckConstraint(
            "rating_medio IS NULL OR (rating_medio >= 0 AND rating_medio <= 5)",
            name="ck_contador_rating",
        ),
        sa.CheckConstraint(
            "total_consultas >= 0",
            name="ck_contador_total_consultas",
        ),
        sa.CheckConstraint(
            "sla_resposta_horas BETWEEN 1 AND 720",
            name="ck_contador_sla_horas",
        ),
        sa.CheckConstraint(
            "crc_numero ~ '^[0-9]{1,9}$'",
            name="ck_contador_crc_numero_formato",
        ),
        sa.CheckConstraint(
            "crc_uf ~ '^[A-Z]{2}$'",
            name="ck_contador_crc_uf_formato",
        ),
        sa.CheckConstraint(
            "cpf IS NULL OR cpf ~ '^[0-9]{11}$'",
            name="ck_contador_cpf_formato",
        ),
        sa.CheckConstraint(
            "cnpj IS NULL OR cnpj ~ '^[0-9]{14}$'",
            name="ck_contador_cnpj_formato",
        ),
        sa.UniqueConstraint("email", name="uq_contador_email"),
        sa.UniqueConstraint(
            "crc_numero", "crc_uf", name="uq_contador_crc",
        ),
    )
    op.create_index(
        "ix_contador_ativo_rating", "contador_parceiro",
        ["ativo", "rating_medio"],
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON contador_parceiro FROM PUBLIC"
    )


def _criar_consulta_marketplace() -> None:
    op.create_table(
        "consulta_marketplace",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "empresa_id", sa.UUID(),
            sa.ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "usuario_id", sa.UUID(),
            sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "contador_id", sa.UUID(),
            sa.ForeignKey("contador_parceiro.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("categoria", sa.String(50), nullable=False),
        sa.Column("pergunta", sa.Text(), nullable=True),
        sa.Column("pergunta_hash", sa.CHAR(64), nullable=False),
        # JsonObject — snapshot determinístico do contexto da empresa no momento
        # da abertura (regime, RBT12, UF, CNAE…). Versionado por snapshot_versao
        # para evolução compatível.
        sa.Column(
            "contexto_empresa_jsonb",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column("snapshot_versao", sa.String(20), nullable=False),
        sa.Column(
            "consentimento_compartilhamento", sa.Boolean(), nullable=False,
        ),
        sa.Column(
            "consentimento_revogado_em",
            sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.Column(
            "pii_apagado_em", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valor_consulta", sa.Numeric(14, 2), nullable=False),
        sa.Column("comissao_plataforma", sa.Numeric(14, 2), nullable=False),
        sa.Column("resposta_resumo", sa.Text(), nullable=True),
        sa.Column(
            "arquivos_anexos", sa.dialects.postgresql.JSONB(), nullable=True,
        ),
        sa.Column("rating_cliente", sa.Integer(), nullable=True),
        sa.Column("comentario_cliente", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("sla_aceitar_ate", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("sla_responder_ate", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "aberta_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("aceita_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("respondida_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paga_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "categoria IN ("
            "'consulta_rapida','analise_intimacao_simples','analise_intimacao_complexa',"
            "'parecer_tecnico','peticao_administrativa','defesa_auto',"
            "'planejamento_tributario','holding','sucessao'"
            ")",
            name="ck_consulta_mkt_categoria",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'aberta','atribuida','aceita','em_andamento',"
            "'concluida','cancelada','expirada'"
            ")",
            name="ck_consulta_mkt_status",
        ),
        sa.CheckConstraint(
            "valor_consulta >= 0",
            name="ck_consulta_mkt_valor",
        ),
        sa.CheckConstraint(
            "comissao_plataforma >= 0 AND comissao_plataforma <= valor_consulta",
            name="ck_consulta_mkt_comissao",
        ),
        sa.CheckConstraint(
            "rating_cliente IS NULL OR rating_cliente BETWEEN 1 AND 5",
            name="ck_consulta_mkt_rating",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_consulta_mkt_idempotency"),
    )
    op.create_index(
        "ix_consulta_mkt_tenant", "consulta_marketplace", ["tenant_id"],
    )
    op.create_index(
        "ix_consulta_mkt_empresa_status", "consulta_marketplace",
        ["empresa_id", "status"],
    )
    op.create_index(
        "ix_consulta_mkt_contador_status", "consulta_marketplace",
        ["contador_id", "status"],
    )
    # Parcial — usado por task de expiração SLA (PR3).
    op.execute(
        "CREATE INDEX ix_consulta_mkt_sla ON consulta_marketplace "
        "(status, sla_responder_ate) "
        "WHERE status IN ('aberta','atribuida','aceita','em_andamento')"
    )

    op.execute("ALTER TABLE consulta_marketplace ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE consulta_marketplace FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY consulta_mkt_tenant ON consulta_marketplace "
        f"USING ({_RLS_TENANT_USING}) "
        f"WITH CHECK ({_RLS_TENANT_USING})"
    )
    op.execute(
        # Parceiro só lê — não cria/responde via INSERT direto, só via UPDATE
        # do contador_id existente (validado em service). WITH CHECK garante
        # que UPDATE não troca a consulta para outro contador.
        f"CREATE POLICY consulta_mkt_parceiro ON consulta_marketplace "
        f"FOR ALL TO marketplace_partner "
        f"USING ({_RLS_PARCEIRO_USING}) "
        f"WITH CHECK ({_RLS_PARCEIRO_USING})"
    )

    # Role do parceiro só vê o que sua policy permite. SELECT/UPDATE ok;
    # INSERT é da role do cliente (fiscal_app); DELETE bloqueado para todos.
    op.execute(
        "GRANT SELECT, UPDATE ON consulta_marketplace TO marketplace_partner"
    )
    op.execute(
        "REVOKE DELETE ON consulta_marketplace FROM PUBLIC"
    )
    # Parceiro também precisa ler o catálogo de outros parceiros? Não — só
    # seu próprio registro via endpoint do PR3 (validação aplicacional).
    op.execute(
        "GRANT SELECT ON contador_parceiro TO marketplace_partner"
    )
