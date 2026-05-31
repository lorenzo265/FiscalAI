"""Sprint 19 PR1 — Índices de performance + pg_stat_statements.

Revision ID: 0041
Revises: 0040
Create Date: 2026-05-26

Sprint 19 = polish + escala. Antes do piloto Lucro Presumido (Sprint 20, 10
empresas reais com apurações trimestrais pesadas), valida latência das queries
hotpath em produção e ativa observabilidade DB-side.

**Entregas:**

1. ``CREATE EXTENSION pg_stat_statements`` — ranking de queries por
   ``total_exec_time``/``mean_exec_time``/``calls``. Base do diagnóstico em
   prod. Assume ``shared_preload_libraries`` configurado em parameter group
   (RDS já carrega por default; self-hosted exige restart do Postgres).

2. **4 índices novos**, todos via ``CREATE INDEX CONCURRENTLY`` em
   ``autocommit_block`` (não bloqueia DML em prod):

   - ``ix_partida_conta_lanc(conta_contabil_id, lancamento_id)`` —
     ``partida_lancamento``. Inverso do ``ix_partida_lanc(lancamento_id,
     ordem)`` existente. Acelera o JOIN de balancete/razão filtrando por
     conta (``RelatoriosService.balancete``, ``.razao``).

   - ``ix_lanc_empresa_comp_status(empresa_id, competencia, status) WHERE
     status IN ('confirmado','encerrado')`` — ``lancamento_contabil``.
     Composto + parcial: balancete e razão filtram com status hard-coded;
     índice parcial reduz tamanho e melhora cache hit ratio.

   - ``ix_saldo_empresa_comp_desc(empresa_id, competencia DESC,
     conta_contabil_id)`` — ``saldo_conta_mes``. DESC ajuda padrão
     last-value-per-group em ``SaldosPeriodoRepo.saldos_posicao_em``
     (Balanço/encerramento anual).

   - ``ix_apuracao_empresa_tipo_comp(empresa_id, tipo, competencia)`` —
     ``apuracao_fiscal``. Adiciona ``tipo`` no início do composto: LP
     trimestral lê 4 tipos (IRPJ/CSLL/PIS/Cofins) × trimestre, e DAS
     mensal filtra ``tipo='das'``. Existente é
     ``ix_apuracao_empresa_comp(empresa_id, competencia)`` — este é
     complementar (tipo como filtro adicional).

**Por que CONCURRENTLY:**

Sem ``CONCURRENTLY``, ``CREATE INDEX`` toma ACCESS EXCLUSIVE LOCK na
tabela — bloqueia INSERTs em prod. Com CONCURRENTLY, índice é construído
em paralelo (mais lento, mas sem lock pesado). **Não roda dentro de
transação** — usamos ``op.get_context().autocommit_block()`` para suspender
o BEGIN/COMMIT automático que o Alembic envolve no ``upgrade()``.

**Princípios cravados:**

  * §8.1 RLS — índices em ``(empresa_id, ...)`` ajudam o planner a
    descer com ``WHERE tenant_id = ...`` quando o caller já fez
    ``SET LOCAL app.tenant_id``. Índices NÃO bypassam RLS (que é por
    linha) — não há ``CREATE POLICY`` aqui.
  * §8.2 Fatos imutáveis — zero ALTER em ``documento_fiscal``,
    ``lancamento_contabil``, ``apuracao_fiscal``. Só ADD INDEX.
  * §8.9 Idempotência — ``IF NOT EXISTS`` em CREATE INDEX e CREATE
    EXTENSION; re-execução é no-op.
  * §8.10 Observabilidade — ``pg_stat_statements`` é fonte primária
    de troubleshooting de latência em prod.
"""

from __future__ import annotations

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Extension — DDL global, idempotente, fora de bloco autocommit.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

    # CREATE INDEX CONCURRENTLY exige fora-de-transação. ``autocommit_block``
    # suspende o BEGIN que o Alembic envolve no ``upgrade()``.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_partida_conta_lanc "
            "ON partida_lancamento (conta_contabil_id, lancamento_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lanc_empresa_comp_status "
            "ON lancamento_contabil (empresa_id, competencia, status) "
            "WHERE status IN ('confirmado', 'encerrado')"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_saldo_empresa_comp_desc "
            "ON saldo_conta_mes (empresa_id, competencia DESC, conta_contabil_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_apuracao_empresa_tipo_comp "
            "ON apuracao_fiscal (empresa_id, tipo, competencia)"
        )


def downgrade() -> None:
    # DROP INDEX CONCURRENTLY também não roda em transação.
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_apuracao_empresa_tipo_comp"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_saldo_empresa_comp_desc"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_lanc_empresa_comp_status"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_partida_conta_lanc"
        )

    # Extension fica — outras migrations futuras podem depender. Não é
    # tabela de domínio nem dado fiscal, drop conservador.
