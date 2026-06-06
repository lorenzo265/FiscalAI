"""Sprint 14 PR1 — Tabela SCD ``aliquota_cbs_ibs`` + seed inicial.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-22

Cria a tabela SCD Type 2 (§8.3) com as alíquotas CBS/IBS por fase da
Reforma Tributária (LC 214/2025). Pool global — sem ``tenant_id`` (igual
às demais tabelas tributárias SCD: ``aliquota_icms_uf``,
``presuncao_lucro_presumido`` etc.).

Seed inicial (3 vigências):

  ┌──────────────────────────┬─────────┬─────────┬──────────────┐
  │ Fase                     │ CBS     │ IBS     │ Vigência     │
  ├──────────────────────────┼─────────┼─────────┼──────────────┤
  │ teste_2026 (informac.)   │ 0,90%   │ 0,10%   │ 2026-01-01   │
  │ transicao_2027_2032      │ 8,80%   │ 0,10%   │ 2027-01-01   │
  │ regime_pleno_2033        │ 8,80%   │ 17,70%  │ 2033-01-01   │
  └──────────────────────────┴─────────┴─────────┴──────────────┘

  Total no pleno (8,80% + 17,70% = 26,5%) bate com a alíquota de referência
  da LC 214/2025 art. 156-A. Repartição CBS/IBS é PRELIMINAR — alíquotas
  finais virão via Comitê Gestor IBS (PLP 68/2024 em tramitação).

  Princípio §8.12: toda saída é labelada "estimativa" no schema de resposta.

Hardening:

  * Trigger SCD reaproveita ``scd_close_previous_valid_to()`` da migration
    0025 com TG_ARGV = (fase, regime, cnae_pattern, classificacao_lc214) —
    fechamento automático de ``valid_to`` da vigência anterior na chave.
  * ``REVOKE UPDATE, DELETE ON aliquota_cbs_ibs FROM PUBLIC`` — princípio
    §8.3 cravado no DB; vigências nunca são editadas in-place.
  * ``GRANT INSERT TO tax_table_admin`` — escritas administrativas futuras
    rodam com este role (criado na migration 0025).
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    _criar_tabela()
    _criar_trigger_scd()
    _grant_revoke()
    _seed_vigencias_iniciais()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_aliquota_cbs_ibs_scd ON aliquota_cbs_ibs;")
    op.drop_table("aliquota_cbs_ibs")


def _criar_tabela() -> None:
    op.create_table(
        "aliquota_cbs_ibs",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("fase", sa.String(30), nullable=False),
        sa.Column("regime", sa.String(20), nullable=True),
        sa.Column("cnae_pattern", sa.String(20), nullable=True),
        sa.Column("classificacao_lc214", sa.String(20), nullable=True),
        sa.Column("aliquota_cbs", sa.Numeric(7, 4), nullable=False),
        sa.Column("aliquota_ibs", sa.Numeric(7, 4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("algoritmo_versao", sa.String(50), nullable=False),
        sa.Column("fonte_norma", sa.String(200), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "aliquota_cbs >= 0 AND aliquota_cbs <= 1",
            name="ck_aliq_cbs_ibs_cbs",
        ),
        sa.CheckConstraint(
            "aliquota_ibs >= 0 AND aliquota_ibs <= 1",
            name="ck_aliq_cbs_ibs_ibs",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_aliq_cbs_ibs_vigencia",
        ),
    )
    op.create_index(
        "ix_aliq_cbs_ibs_lookup", "aliquota_cbs_ibs",
        ["fase", "valid_from"],
    )


def _criar_trigger_scd() -> None:
    """Reaproveita a função genérica criada na migration 0025."""
    op.execute("DROP TRIGGER IF EXISTS trg_aliquota_cbs_ibs_scd ON aliquota_cbs_ibs;")
    op.execute(
        """
        CREATE TRIGGER trg_aliquota_cbs_ibs_scd
        AFTER INSERT ON aliquota_cbs_ibs
        FOR EACH ROW
        EXECUTE FUNCTION scd_close_previous_valid_to(
          'fase', 'regime', 'cnae_pattern', 'classificacao_lc214'
        );
        """
    )


def _grant_revoke() -> None:
    """Cravamento do princípio §8.3 no DB: SCD é append-only via INSERT."""
    op.execute("GRANT INSERT ON aliquota_cbs_ibs TO tax_table_admin;")
    op.execute("REVOKE UPDATE, DELETE ON aliquota_cbs_ibs FROM PUBLIC;")


def _seed_vigencias_iniciais() -> None:
    """3 vigências cobrindo todo o cronograma LC 214/2025 (até 2033+)."""
    tabela = sa.table(
        "aliquota_cbs_ibs",
        sa.column("fase", sa.String),
        sa.column("regime", sa.String),
        sa.column("cnae_pattern", sa.String),
        sa.column("classificacao_lc214", sa.String),
        sa.column("aliquota_cbs", sa.Numeric),
        sa.column("aliquota_ibs", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("algoritmo_versao", sa.String),
        sa.column("fonte_norma", sa.String),
        sa.column("observacao", sa.Text),
    )
    seed = "reforma.cbs-ibs.v1"
    op.bulk_insert(
        tabela,
        [
            # ── 2026 — período de teste informacional ──────────────────────
            {
                "fase": "teste_2026",
                "regime": None,
                "cnae_pattern": None,
                "classificacao_lc214": None,
                "aliquota_cbs": "0.0090",
                "aliquota_ibs": "0.0010",
                "valid_from": datetime.date(2026, 1, 1),
                "valid_to": None,
                "algoritmo_versao": seed,
                "fonte_norma": "LC 214/2025 art. 348 §3º (cobranca-teste 2026)",
                "observacao": (
                    "Informacional — coexiste com PIS/Cofins/ICMS/ISS sem "
                    "recolhimento separado. Total 1,0% sobre a base."
                ),
            },
            # ── 2027–2032 — transição (CBS plena substitui PIS+Cofins) ────
            {
                "fase": "transicao_2027_2032",
                "regime": None,
                "cnae_pattern": None,
                "classificacao_lc214": None,
                "aliquota_cbs": "0.0880",
                "aliquota_ibs": "0.0010",
                "valid_from": datetime.date(2027, 1, 1),
                "valid_to": None,
                "algoritmo_versao": seed,
                "fonte_norma": (
                    "LC 214/2025 art. 349 (CBS plena substitui PIS+Cofins; "
                    "IBS-teste 0,1%)"
                ),
                "observacao": (
                    "Preliminar — PLP 68/2024 em tramitação. ICMS+ISS ainda "
                    "ativos com redução gradual."
                ),
            },
            # ── 2033+ — regime pleno (IBS plenamente substitui ICMS+ISS) ──
            {
                "fase": "regime_pleno_2033",
                "regime": None,
                "cnae_pattern": None,
                "classificacao_lc214": None,
                "aliquota_cbs": "0.0880",
                "aliquota_ibs": "0.1770",
                "valid_from": datetime.date(2033, 1, 1),
                "valid_to": None,
                "algoritmo_versao": seed,
                "fonte_norma": (
                    "LC 214/2025 art. 156-A §1º — alíquota de referência "
                    "preliminar 26,5%"
                ),
                "observacao": (
                    "Estimativa — alíquotas finais via Comitê Gestor IBS. "
                    "Repartição CBS 8,80% + IBS 17,70% (total 26,5%)."
                ),
            },
        ],
    )
