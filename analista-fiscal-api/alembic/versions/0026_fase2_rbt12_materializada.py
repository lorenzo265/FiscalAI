"""Fase 2 PR3 — View materializada ``rbt12_mensal`` substitui ``empresa.faturamento_12m``.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-19

Princípio: §8.8 (LLM nunca escreve fatos) + §8.3 (decisões versionadas) ganham
um caso adicional — a RBT12 (Receita Bruta dos últimos 12 meses, base do
Simples Nacional) deixa de ser **declarada manualmente** em
``empresa.faturamento_12m`` e passa a ser **derivada** de
``documento_fiscal`` autorizado e vigente.

Mecânica:

  1. Materialized View ``rbt12_mensal(tenant_id, empresa_id, competencia, valor)``
     agrega ``documento_fiscal.valor_total`` por (empresa, mês),
     depois soma janela ROWS 11 PRECEDING — última linha por empresa
     = soma das 12 emissões mais recentes.

     Filtro: ``direcao='saida' AND status='autorizada' AND superseded_by IS NULL``.

  2. UNIQUE INDEX ``(tenant_id, empresa_id, competencia)`` — pré-requisito
     para ``REFRESH MATERIALIZED VIEW CONCURRENTLY``.

  3. Função ``refresh_rbt12_mensal()`` ``SECURITY DEFINER`` —
     chamada pelo worker Celery mensal (`rbt12.refresh_mensal`, dia 2 às 6h,
     após encerramento contábil). Roda como owner para bypassar RLS na
     leitura de ``documento_fiscal`` (que tem FORCE ROW LEVEL SECURITY).

Limitação consciente (documentada para Fase 5):
  * Para empresa sazonal (não emite todo mês), a janela
    ``ROWS BETWEEN 11 PRECEDING`` cobre 12 emissões — pode abranger
    período calendário maior que 12 meses. Trade-off aceito: para PME
    típica brasileira que emite mensalmente, é exato.
  * Empresa nova sem documentos: MV não retorna linha. O service faz
    fallback para ``empresa.faturamento_12m`` (declarado no onboarding).

Drop da coluna ``empresa.faturamento_12m`` fica para migration 0027
(2ª fase do drop em 2 fases — esta migration é a "soft deprecation":
view + endpoints migrados; depois drop).
"""

from __future__ import annotations

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | None = None
depends_on: str | None = None


_MV_QUERY = """
CREATE MATERIALIZED VIEW rbt12_mensal AS
WITH receita_mensal AS (
    SELECT
        tenant_id,
        empresa_id,
        date_trunc('month', emitida_em)::date AS competencia,
        SUM(valor_total) AS valor_mes
    FROM documento_fiscal
    WHERE direcao = 'saida'
      AND status = 'autorizada'
      AND superseded_by IS NULL
    GROUP BY tenant_id, empresa_id, date_trunc('month', emitida_em)
)
SELECT
    tenant_id,
    empresa_id,
    competencia,
    SUM(valor_mes) OVER (
        PARTITION BY tenant_id, empresa_id
        ORDER BY competencia
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    ) AS valor
FROM receita_mensal
WITH DATA;
"""


_REFRESH_FN = """
CREATE OR REPLACE FUNCTION refresh_rbt12_mensal()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $fn$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY rbt12_mensal;
END;
$fn$;
"""


def upgrade() -> None:
    op.execute(_MV_QUERY)
    op.execute(
        "CREATE UNIQUE INDEX uq_rbt12_mensal_chave"
        " ON rbt12_mensal (tenant_id, empresa_id, competencia);"
    )
    op.execute(
        "CREATE INDEX ix_rbt12_mensal_empresa_comp"
        " ON rbt12_mensal (empresa_id, competencia DESC);"
    )
    op.execute(_REFRESH_FN)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refresh_rbt12_mensal();")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS rbt12_mensal;")
