"""Fase 2 PR2 — Hardening das 8 tabelas SCD tributárias (princípio §8.3).

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-19

Cole o princípio invioólavel §8.3 (decisões versionadas) ao schema: tabelas
tributárias SCD Type 2 deixam de aceitar UPDATE/DELETE do role público;
nova vigência só entra como nova linha (INSERT), e o ``valid_to`` da linha
anterior é fechado automaticamente por trigger.

Tabelas afetadas (8):

  SCD Type 2 com (valid_from, valid_to)  — recebem trigger + REVOKE:
    * tabela_simples_faixa     — chave (anexo, faixa)
    * tabela_inss_faixa        — chave (tipo, faixa)
    * tabela_irrf_faixa        — chave (faixa,)
    * tabela_fgts_aliquota     — chave (vinculo,)
    * tabela_depreciacao_rfb   — chave (categoria,)
    * presuncao_lucro_presumido — chave (grupo_atividade, cnae_pattern)
    * aliquota_icms_uf         — chave (uf,)

  Append-only puro (sem valid_to) — só recebe REVOKE:
    * selic_mensal             — UNIQUE(competencia); cada mês é nova linha.

Mecanismo:

  1. Função PL/pgSQL genérica ``scd_close_previous_valid_to()``:
     * Recebe os nomes das colunas-chave via ``TG_ARGV``.
     * Usa ``to_jsonb(NEW)`` para acessar valores dinamicamente.
     * Trata NULL com ``IS NOT DISTINCT FROM`` (importante para
       ``presuncao_lucro_presumido.cnae_pattern``).
     * Executa ``UPDATE`` dinâmico fechando ``valid_to`` da vigência
       anterior aberta com mesma chave de domínio e ``valid_from`` menor.
     * ``SECURITY DEFINER`` — roda como owner para bypassar o REVOKE.

  2. Trigger ``trg_<tabela>_scd`` ``AFTER INSERT`` em cada uma das 7 tabelas SCD.

  3. Role ``tax_table_admin`` (sinalização semântica):
     * ``GRANT INSERT ON <8 tabelas> TO tax_table_admin`` (explícito).
     * Aplicação continua inserindo via PUBLIC (não foi revogado INSERT),
       mas escritas administrativas futuras devem rodar com este role.

  4. ``REVOKE UPDATE, DELETE ON <8 tabelas> FROM PUBLIC``.
     SELECT preserva-se (consumo público). INSERT preserva-se (seeds + nova vigência).
"""

from __future__ import annotations

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | None = None
depends_on: str | None = None


_SCD_TABLES: dict[str, tuple[str, ...]] = {
    "tabela_simples_faixa": ("anexo", "faixa"),
    "tabela_inss_faixa": ("tipo", "faixa"),
    "tabela_irrf_faixa": ("faixa",),
    "tabela_fgts_aliquota": ("vinculo",),
    "tabela_depreciacao_rfb": ("categoria",),
    "presuncao_lucro_presumido": ("grupo_atividade", "cnae_pattern"),
    "aliquota_icms_uf": ("uf",),
}

_APPEND_ONLY_TABLES: tuple[str, ...] = ("selic_mensal",)

_ALL_PROTECTED: tuple[str, ...] = (*_SCD_TABLES.keys(), *_APPEND_ONLY_TABLES)


_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION scd_close_previous_valid_to()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $fn$
DECLARE
  key_col      TEXT;
  where_parts  TEXT[];
  new_json     JSONB := to_jsonb(NEW);
  full_where   TEXT;
  prev_to      DATE;
  new_from_txt TEXT := new_json ->> 'valid_from';
BEGIN
  -- defensivo: SCD trigger só faz sentido se valid_from está preenchido
  IF new_from_txt IS NULL THEN
    RETURN NEW;
  END IF;

  prev_to := (new_from_txt::date - INTERVAL '1 day')::date;

  where_parts := ARRAY[
    'valid_to IS NULL',
    format('valid_from < %L', new_from_txt)
  ];

  FOREACH key_col IN ARRAY TG_ARGV LOOP
    IF (new_json -> key_col) IS NULL OR (new_json -> key_col) = 'null'::jsonb THEN
      where_parts := where_parts || format('%I IS NULL', key_col);
    ELSE
      where_parts := where_parts || format(
        '%I IS NOT DISTINCT FROM %L',
        key_col,
        new_json ->> key_col
      );
    END IF;
  END LOOP;

  full_where := array_to_string(where_parts, ' AND ');

  EXECUTE format(
    'UPDATE %I SET valid_to = %L WHERE %s',
    TG_TABLE_NAME, prev_to, full_where
  );

  RETURN NEW;
END;
$fn$;
"""


def upgrade() -> None:
    # ─── 1) Função genérica do trigger ───────────────────────────────────────
    op.execute(_TRIGGER_FN)

    # ─── 2) Role administrativo (sinalização semântica) ──────────────────────
    op.execute(
        """
        DO $do$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_table_admin') THEN
            CREATE ROLE tax_table_admin NOLOGIN;
          END IF;
        END
        $do$;
        """
    )

    # ─── 3) Trigger por tabela SCD + GRANT INSERT explícito ──────────────────
    for table, key_cols in _SCD_TABLES.items():
        args_sql = ", ".join(f"'{c}'" for c in key_cols)
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_scd ON {table};"
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_scd
            AFTER INSERT ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION scd_close_previous_valid_to({args_sql});
            """
        )

    for table in _ALL_PROTECTED:
        op.execute(f"GRANT INSERT ON {table} TO tax_table_admin;")

    # ─── 4) REVOKE UPDATE, DELETE FROM PUBLIC ────────────────────────────────
    for table in _ALL_PROTECTED:
        op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM PUBLIC;")


def downgrade() -> None:
    # Reativa UPDATE/DELETE para PUBLIC
    for table in _ALL_PROTECTED:
        op.execute(f"GRANT UPDATE, DELETE ON {table} TO PUBLIC;")
        op.execute(f"REVOKE INSERT ON {table} FROM tax_table_admin;")

    # Remove triggers
    for table in _SCD_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_scd ON {table};")

    # Remove função e role
    op.execute("DROP FUNCTION IF EXISTS scd_close_previous_valid_to();")
    op.execute(
        """
        DO $do$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_table_admin') THEN
            DROP ROLE tax_table_admin;
          END IF;
        END
        $do$;
        """
    )
