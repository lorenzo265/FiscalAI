"""IRRF 2026 — nova vigência SCD da tabela progressiva mensal + redutor.

Revision ID: 0059
Revises: 0058
Create Date: 2026-06-21

Fecha PARCIALMENTE a pendência #9 do `log_agente.md` (agora o IRRF) e o
achado 🔴 #1 do auto de infração 2026-06-21
(`docs/auditoria-fiscal/auto-de-infracao-2026-06-21.md`).

PROBLEMA CORRIGIDO
------------------
A `tabela_irrf_faixa` estava seedada SÓ na vigência fev/2024 (migration 0016,
``valid_from=2024-02-01, valid_to=NULL``, isento até R$ 2.259,20). Desde
01/01/2026 isso retém IRRF A MAIOR na base da pirâmide (a faixa isenta subiu
para R$ 2.428,80 e a Lei 15.270/2025 ainda zera a retenção efetiva até
R$ 5.000,00 de rendimento tributável mensal).

Esta migration insere a vigência 2026 da TABELA PROGRESSIVA (Lei 15.191/2025).
O REDUTOR da Lei 15.270/2025 é um mecanismo de cálculo (aplicado APÓS a tabela,
sobre o rendimento tributável, com piso 0) — NÃO cabe em colunas de faixa; vive
em `app/modules/pessoal/calcula_irrf.py` como constantes legais nomeadas e
citadas (ver nota "ESCOPO" abaixo).

FONTE OFICIAL (primária, citável)
---------------------------------
  * Tabela progressiva mensal 2026 (faixas/alíquotas/parcela a deduzir,
    dedução por dependente, desconto simplificado): LEI 15.191/2025
    (inalterada desde a competência maio/2025). Confirmada na página oficial
    da RFB "Meu Imposto de Renda » Tabelas".
  * Redutor mensal da retenção (faixa R$ 5.000–7.350): LEI 15.270/2025,
    vigência 01/01/2026. Exemplos resolvidos confirmados na página oficial:
    https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/exemplos-de-aplicacao-da-lei-15-270-2025

TABELA PROGRESSIVA MENSAL 2026 (Lei 15.191/2025)
------------------------------------------------
  faixa 1 — até R$ 2.428,80   → 0,0%   parcela a deduzir R$ 0,00
  faixa 2 — até R$ 2.826,65   → 7,5%   parcela a deduzir R$ 182,16
  faixa 3 — até R$ 3.751,05   → 15,0%  parcela a deduzir R$ 394,16
  faixa 4 — até R$ 4.664,68   → 22,5%  parcela a deduzir R$ 675,49
  faixa 5 — acima de 4.664,68 → 27,5%  parcela a deduzir R$ 908,73
  Dedução por dependente: R$ 189,59.
  Desconto simplificado mensal: R$ 607,20 (= 25% × 2.428,80, teto da faixa 1).

  Continuidade conferida à mão (cada parcela mantém o imposto contínuo no
  limite de faixa): 2428,80×7,5% = 182,16 ✓ ; faixa 3: 394,16 ✓ ;
  faixa 4: 675,49 ✓ ; faixa 5: 908,73 ✓.

MECANISMO SCD (§8.3)
--------------------
  * INSERT das 5 faixas com ``valid_from='2026-01-01', valid_to=NULL``.
  * A chave SCD de ``tabela_irrf_faixa`` é ``(faixa,)`` (migration 0025).
    O trigger ``scd_close_previous_valid_to`` fecha o ``valid_to`` da vigência
    fev/2024 (mesma ``faixa``, ``valid_from < 2026-01-01``) para ``2025-12-31``
    AUTOMATICAMENTE. NUNCA fazemos UPDATE/DELETE manual em linha seedada — o DB
    tem ``REVOKE UPDATE, DELETE FROM PUBLIC`` nessas tabelas (migration 0025).

ESCOPO — o que NÃO entra aqui
-----------------------------
  * O REDUTOR (Lei 15.270/2025) não é seedado em coluna: o schema
    ``tabela_irrf_faixa`` modela só faixas progressivas. O redutor (linear
    978,62 − 0,133145×rendimento, faixa 5.000–7.350; isenção efetiva ≤ 5.000)
    é constante legal nomeada em ``calcula_irrf.py`` (com fonte e vigência).
    Preferimos isso a alterar o schema (instrução do gate).
  * GAP RETROATIVO mai–dez/2025: a tabela progressiva mudou em maio/2025
    (Lei 15.191/2025) e NUNCA foi seedada — a vigência fev/2024 ficou aberta o
    ano inteiro de 2025. Esta migration NÃO corrige esse buraco histórico
    (exigiria uma vigência 2025-05-01 fechada em 2025-12-31, decisão à parte).
    Registrado como pendência SEPARADA. Aqui só abrimos a vigência 2026.

Princípios cravados: §8.3 (SCD Type 2, histórico 2024 preservado),
§8.4 (golden test com valores oficiais bloqueando regressão).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | None = None
depends_on: str | None = None


_FONTE_IRRF_2026 = "Lei 15.191/2025 (tabela progressiva mensal vigente em 2026)"
_DEP_2026 = "189.59"
# Teto simbólico da faixa 5 ("acima de 4.664,68"). Mesmo padrão do seed 0016.
_TETO_SIMBOLICO = "999999999.99"


def upgrade() -> None:
    irrf_t = sa.table(
        "tabela_irrf_faixa",
        sa.column("faixa", sa.Integer),
        sa.column("base_ate", sa.Numeric),
        sa.column("aliquota", sa.Numeric),
        sa.column("parcela_deduzir", sa.Numeric),
        sa.column("deducao_dependente", sa.Numeric),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("fonte", sa.String),
    )
    # valid_to=None: o trigger scd_close_previous_valid_to fecha a vigência
    # fev/2024 anterior (mesma chave (faixa,)) em 2025-12-31. Não tocamos nela.
    op.bulk_insert(
        irrf_t,
        [
            {
                "faixa": 1, "base_ate": "2428.80", "aliquota": "0.0000",
                "parcela_deduzir": "0.00", "deducao_dependente": _DEP_2026,
                "valid_from": "2026-01-01", "valid_to": None,
                "fonte": _FONTE_IRRF_2026,
            },
            {
                "faixa": 2, "base_ate": "2826.65", "aliquota": "0.0750",
                "parcela_deduzir": "182.16", "deducao_dependente": _DEP_2026,
                "valid_from": "2026-01-01", "valid_to": None,
                "fonte": _FONTE_IRRF_2026,
            },
            {
                "faixa": 3, "base_ate": "3751.05", "aliquota": "0.1500",
                "parcela_deduzir": "394.16", "deducao_dependente": _DEP_2026,
                "valid_from": "2026-01-01", "valid_to": None,
                "fonte": _FONTE_IRRF_2026,
            },
            {
                "faixa": 4, "base_ate": "4664.68", "aliquota": "0.2250",
                "parcela_deduzir": "675.49", "deducao_dependente": _DEP_2026,
                "valid_from": "2026-01-01", "valid_to": None,
                "fonte": _FONTE_IRRF_2026,
            },
            {
                "faixa": 5, "base_ate": _TETO_SIMBOLICO, "aliquota": "0.2750",
                "parcela_deduzir": "908.73", "deducao_dependente": _DEP_2026,
                "valid_from": "2026-01-01", "valid_to": None,
                "fonte": _FONTE_IRRF_2026,
            },
        ],
    )


def downgrade() -> None:
    # Remove as 5 linhas 2026 seedadas. O downgrade NÃO reabre as linhas fev/2024
    # (fechadas pelo trigger no upgrade) — reverter o valid_to=2025-12-31 para
    # NULL exigiria UPDATE em linha seedada (proibido §8.3 / REVOKE). Em prod o
    # caminho é forward-only; este DELETE serve só para DB scratch/CI.
    op.execute(
        "DELETE FROM tabela_irrf_faixa "
        "WHERE valid_from = DATE '2026-01-01' "
        "  AND fonte = 'Lei 15.191/2025 (tabela progressiva mensal vigente em 2026)'"
    )
