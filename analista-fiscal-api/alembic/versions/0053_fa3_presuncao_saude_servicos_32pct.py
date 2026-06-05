"""FA3/M6 — Presunção LP 32%/32% para saúde não-hospitalar + serviços.

Revision ID: 0053
Revises: 0052
Create Date: 2026-06-04

Problema: seed 0019 mapeia 32% para CNAEs 69/71/73/70/74/82.  Os grupos
de saúde não-hospitalar (86.2x / 86.3x / 86.4x / 86.5x / 86.6x / 86.9x),
veterinária (75), cursos/treinamento (855) e serviços pessoais (96) foram
listados no docstring de 0019 mas NÃO foram inseridos, caindo no default
``comercio_industria`` (8%/12%) — incorreto.

Base legal:
  * Lei 9.249/1995 art. 15 §1º III (IRPJ 32%) + art. 20 (CSLL 32%):
    "prestação de serviços em geral, exceto serviços hospitalares e de
    transporte, assim entendidas as atividades de … profissões liberais,
    mediação, intermediação, custeio ou benefício."
  * IN RFB 1.700/2017 art. 33 III — "prestação de serviços em geral" = 32%.

Estrutura da divisão 86 CNAE 2.3 (IBGE) e sua presunção:
  * 8610 → hospitais (seed 0019, 8%/12%) — NÃO tocado aqui.
  * 8621/8622/8629 → medicina e odontologia ambulatorial (32%/32%).
  * 8630 → clínicas e consultórios médicos e odontológicos (32%/32%).
  * 8640 → atividades de serviços de diagnóstico (32%/32%).
  * 8650 → profissionais da área de saúde (exceto médicos) (32%/32%).
  * 8660 → atividades de atenção à saúde humana não especif. (32%/32%).
  * 8690 → outras atividades de atenção à saúde humana (32%/32%).

Estratégia de prefix-match (normalizado sem ponto/traço):
  - "862" captura 8621/8622/8629.
  - "863" captura 8630.
  - "864" captura 8640.
  - "865" captura 8650/8651/8652.
  - "866" captura 8660.
  - "869" captura 8690.
  Cada um com prioridade 15, igual aos 32% do 0019.  O pattern "8610"
  do seed 0019 (prioridade 20) continua funcionando — "8610x" começa
  com "8610", mas NÃO começa com "862"/"863"/"864" etc.

Patterns inseridos (prefixo CNAE IBGE 2.3, após _normalizar_cnae):
  ┌─────────────────────────────┬───────┬───────┬───────────────────────────┐
  │ grupo_atividade             │ IRPJ% │ CSLL% │ Descrição CNAE            │
  ├─────────────────────────────┼───────┼───────┼───────────────────────────┤
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 862 — medicina ambulat.   │
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 863 — consultórios méd.   │
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 864 — serv. diagnóstico   │
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 865 — profis. saúde       │
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 866 — at. saúde n. espec. │
  │ saude_nao_hospitalar        │ 32%   │ 32%   │ 869 — outras at. saúde    │
  │ servicos_profissionais      │ 32%   │ 32%   │ 75  — veterinária         │
  │ servicos_profissionais      │ 32%   │ 32%   │ 855 — cursos/treinamento  │
  │ servicos_pessoais           │ 32%   │ 32%   │ 96  — serviços pessoais   │
  └─────────────────────────────┴───────┴───────┴───────────────────────────┘

Vigência SCD: ``valid_from = 1996-01-01`` (mesma das linhas de 0019,
coerente com Lei 9.249/1995 vigente desde jan/1996). Não altera histórico.

Sem RLS: tabela pública (ver 0019 — sem ``tenant_id``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | None = None
depends_on: str | None = None

_FONTE = "Lei 9.249/1995 art. 15 §1º III + art. 20 + IN RFB 1.700/2017 art. 33"
_VALID_FROM = "1996-01-01"
_IRPJ_32 = "0.3200"
_CSLL_32 = "0.3200"

# Novos patterns a inserir — nunca alterar os existentes (SCD imutável).
_NOVOS_GRUPOS: list[dict[str, object]] = [
    # ── Saúde não-hospitalar — 32%/32% ────────────────────────────────────
    # art. 15 §1º III e art. 20: serviços profissionais de saúde que NÃO são
    # hospitalares (estes ficam em 8% / grupo servicos_hospitalares do 0019).
    # Prioridade 15 (número menor = maior precedência). O pattern "8610" do
    # 0019 (prioridade 20) captura hospitais; nenhum dos novos prefixos abaixo
    # captura "8610x" — isolamento garantido.
    #
    # "862" → 8621 (medicina amb.), 8622 (odonto amb.), 8629 (outros amb.).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "862",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # "863" → 8630 (consultórios e clínicas médicas e odontológicas).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "863",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # "864" → 8640 (laboratórios de diagnóstico por imagem/análises clínicas).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "864",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # "865" → 8650 (profissionais de saúde: psicólogos, fisioter., fonoaud.).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "865",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # "866" → 8660 (atividades de atenção à saúde humana não especif. prev.).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "866",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # "869" → 8690 (outras atividades de atenção à saúde humana).
    {
        "grupo_atividade": "saude_nao_hospitalar",
        "cnae_pattern": "869",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # ── Veterinária (75) — 32%/32% ─────────────────────────────────────────
    # CNAE 7500 (atividades veterinárias). Profissão liberal = 32%.
    {
        "grupo_atividade": "servicos_profissionais",
        "cnae_pattern": "75",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # ── Cursos e treinamento (855) — 32%/32% ───────────────────────────────
    # CNAE 8550 (atividades de apoio à educação / treinamento profissional).
    # Prestação de serviços = 32%.
    {
        "grupo_atividade": "servicos_profissionais",
        "cnae_pattern": "855",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
    # ── Serviços pessoais (96) — 32%/32% ───────────────────────────────────
    # CNAE 9601 (lavanderias), 9602 (cabeleireiros), 9609 (outros serviços
    # pessoais). Prestação de serviços pessoais = 32%.
    {
        "grupo_atividade": "servicos_pessoais",
        "cnae_pattern": "96",
        "percentual_irpj": _IRPJ_32,
        "percentual_csll": _CSLL_32,
        "limite_receita_anual": None,
        "prioridade": 15,
        "fonte": _FONTE,
        "valid_from": _VALID_FROM,
        "valid_to": None,
    },
]


def upgrade() -> None:
    tabela = sa.table(
        "presuncao_lucro_presumido",
        sa.column("grupo_atividade", sa.String),
        sa.column("cnae_pattern", sa.String),
        sa.column("percentual_irpj", sa.Numeric),
        sa.column("percentual_csll", sa.Numeric),
        sa.column("limite_receita_anual", sa.Numeric),
        sa.column("prioridade", sa.Integer),
        sa.column("fonte", sa.String),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
    )
    op.bulk_insert(tabela, _NOVOS_GRUPOS)


def downgrade() -> None:
    """Remove apenas as linhas inseridas por esta migration.

    Filtra por ``cnae_pattern`` e ``valid_from`` para garantir que somente
    os registros deste seed sejam removidos — sem tocar nas linhas do 0019.
    """
    conn = op.get_bind()
    patterns = [str(r["cnae_pattern"]) for r in _NOVOS_GRUPOS]
    conn.execute(
        sa.text(
            "DELETE FROM presuncao_lucro_presumido "
            "WHERE cnae_pattern = ANY(:patterns) "
            "  AND valid_from = :valid_from"
        ),
        {"patterns": patterns, "valid_from": _VALID_FROM},
    )
