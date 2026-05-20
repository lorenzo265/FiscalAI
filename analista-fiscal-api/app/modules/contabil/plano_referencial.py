"""Plano de contas referencial mínimo brasileiro (Sprint 9 PR1).

Inspirado no Plano de Contas Referencial PJ da Receita Federal (publicado no
SPED ECD). 36 contas (sintéticas + analíticas) que cobrem o MVP:

* Ativo circulante (caixa, banco, clientes, estoque).
* Ativo não-circulante (imobilizado + depreciação acumulada).
* Passivo (fornecedores, salários, INSS, FGTS, provisões trabalhistas).
* PL (capital, lucros acumulados, resultado do exercício).
* Receitas (vendas serviços, vendas mercadorias).
* Despesas (CMV, salários, encargos, depreciação, impostos).

Cada item: ``(codigo, descricao, parent_codigo, natureza, tipo, aceita_lancamento, codigo_ecd)``.

O motor de lançamentos automáticos (PR2) usa códigos específicos como
"1.1.1.02" (banco) ou "4.1.01.01" (CMV) — manter chaves estáveis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ItemPlano:
    codigo: str
    descricao: str
    parent_codigo: str | None
    natureza: str  # 'D' | 'C'
    tipo: str
    aceita_lancamento: bool
    codigo_ecd_referencial: str | None
    nivel: int


# ── Plano referencial ────────────────────────────────────────────────────────


PLANO_REFERENCIAL: tuple[ItemPlano, ...] = (
    # ── 1. ATIVO (natureza D) ───────────────────────────────────────────────
    ItemPlano("1", "ATIVO", None, "D", "ativo", False, "1", 1),
    ItemPlano("1.1", "ATIVO CIRCULANTE", "1", "D", "ativo", False, "1.01", 2),
    ItemPlano("1.1.1", "Disponibilidades", "1.1", "D", "ativo", False, "1.01.01", 3),
    ItemPlano(
        "1.1.1.01", "Caixa", "1.1.1", "D", "ativo", True, "1.01.01.01.01.01", 4
    ),
    ItemPlano(
        "1.1.1.02",
        "Bancos Conta Movimento",
        "1.1.1",
        "D",
        "ativo",
        True,
        "1.01.01.02.01.01",
        4,
    ),
    ItemPlano(
        "1.1.2", "Clientes / Contas a Receber", "1.1", "D", "ativo", False, "1.01.02", 3
    ),
    ItemPlano(
        "1.1.2.01",
        "Duplicatas a Receber",
        "1.1.2",
        "D",
        "ativo",
        True,
        "1.01.02.02.01.01",
        4,
    ),
    ItemPlano("1.1.3", "Estoques", "1.1", "D", "ativo", False, "1.01.04", 3),
    ItemPlano(
        "1.1.3.01", "Mercadorias", "1.1.3", "D", "ativo", True, "1.01.04.01.01.01", 4
    ),
    ItemPlano(
        "1.2", "ATIVO NÃO CIRCULANTE", "1", "D", "ativo", False, "1.02", 2
    ),
    ItemPlano(
        "1.2.3", "Imobilizado", "1.2", "D", "ativo", False, "1.02.03", 3
    ),
    ItemPlano(
        "1.2.3.01",
        "Imobilizado — Bens",
        "1.2.3",
        "D",
        "ativo",
        True,
        "1.02.03.01.01.01",
        4,
    ),
    ItemPlano(
        "1.2.3.99",
        "(-) Depreciação Acumulada",
        "1.2.3",
        "C",
        "ativo",
        True,
        "1.02.03.09.01.01",
        4,
    ),
    # ── 2. PASSIVO (natureza C) ─────────────────────────────────────────────
    ItemPlano("2", "PASSIVO", None, "C", "passivo", False, "2", 1),
    ItemPlano(
        "2.1", "PASSIVO CIRCULANTE", "2", "C", "passivo", False, "2.01", 2
    ),
    ItemPlano(
        "2.1.1", "Fornecedores", "2.1", "C", "passivo", False, "2.01.01", 3
    ),
    ItemPlano(
        "2.1.1.01",
        "Fornecedores Nacionais",
        "2.1.1",
        "C",
        "passivo",
        True,
        "2.01.01.01.01.01",
        4,
    ),
    ItemPlano(
        "2.1.2", "Obrigações Trabalhistas", "2.1", "C", "passivo", False, "2.01.02", 3
    ),
    ItemPlano(
        "2.1.2.01",
        "Salários a Pagar",
        "2.1.2",
        "C",
        "passivo",
        True,
        "2.01.02.01.01.01",
        4,
    ),
    ItemPlano(
        "2.1.2.02",
        "Provisão de Férias",
        "2.1.2",
        "C",
        "passivo",
        True,
        "2.01.02.02.01.01",
        4,
    ),
    ItemPlano(
        "2.1.2.03",
        "Provisão 13º Salário",
        "2.1.2",
        "C",
        "passivo",
        True,
        "2.01.02.02.02.01",
        4,
    ),
    ItemPlano(
        "2.1.3", "Encargos a Recolher", "2.1", "C", "passivo", False, "2.01.03", 3
    ),
    ItemPlano(
        "2.1.3.01",
        "INSS a Recolher",
        "2.1.3",
        "C",
        "passivo",
        True,
        "2.01.03.01.01.01",
        4,
    ),
    ItemPlano(
        "2.1.3.02",
        "FGTS a Recolher",
        "2.1.3",
        "C",
        "passivo",
        True,
        "2.01.03.02.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4", "Impostos a Recolher", "2.1", "C", "passivo", False, "2.01.04", 3
    ),
    ItemPlano(
        "2.1.4.01",
        "DAS Simples Nacional",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.99.01.01",
        4,
    ),
    # ── 3. PATRIMÔNIO LÍQUIDO (natureza C) ──────────────────────────────────
    ItemPlano(
        "3", "PATRIMÔNIO LÍQUIDO", None, "C", "patrimonio_liquido", False, "3", 1
    ),
    ItemPlano(
        "3.1", "Capital Social", "3", "C", "patrimonio_liquido", False, "3.01", 2
    ),
    ItemPlano(
        "3.1.01",
        "Capital Social Subscrito",
        "3.1",
        "C",
        "patrimonio_liquido",
        True,
        "3.01.01.01.01.01",
        3,
    ),
    ItemPlano(
        "3.9",
        "Lucros / Prejuízos Acumulados",
        "3",
        "C",
        "patrimonio_liquido",
        False,
        "3.07",
        2,
    ),
    ItemPlano(
        "3.9.01",
        "Resultado do Exercício",
        "3.9",
        "C",
        "patrimonio_liquido",
        True,
        "3.07.01.01.01.01",
        3,
    ),
    # ── 4. RECEITAS (natureza C) ────────────────────────────────────────────
    ItemPlano("4", "RECEITAS", None, "C", "receita", False, "4", 1),
    ItemPlano(
        "4.1", "Receita Operacional", "4", "C", "receita", False, "4.01", 2
    ),
    ItemPlano(
        "4.1.01",
        "Receita de Serviços",
        "4.1",
        "C",
        "receita",
        True,
        "4.01.01.01.01.01",
        3,
    ),
    ItemPlano(
        "4.1.02",
        "Receita de Vendas",
        "4.1",
        "C",
        "receita",
        True,
        "4.01.01.02.01.01",
        3,
    ),
    ItemPlano(
        "4.9",
        "Outras Receitas",
        "4",
        "C",
        "receita",
        False,
        "4.01.99",
        2,
    ),
    ItemPlano(
        "4.9.99",
        "Outras Receitas — A Classificar",
        "4.9",
        "C",
        "receita",
        True,
        "4.01.99.01.01.01",
        3,
    ),
    # ── 5. DESPESAS (natureza D) ────────────────────────────────────────────
    ItemPlano("5", "DESPESAS", None, "D", "despesa", False, "4.99", 1),
    ItemPlano(
        "5.1", "Custos / Despesas Operacionais", "5", "D", "despesa", False, "4.02", 2
    ),
    ItemPlano(
        "5.1.01",
        "CMV — Custo de Mercadoria Vendida",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.01.01.01.01",
        3,
    ),
    ItemPlano(
        "5.1.02",
        "Despesas com Pessoal",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.02.01.01.01",
        3,
    ),
    ItemPlano(
        "5.1.03",
        "Encargos Sociais",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.02.02.01.01",
        3,
    ),
    ItemPlano(
        "5.1.04",
        "Despesa de Depreciação",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.05.01.01.01",
        3,
    ),
    ItemPlano(
        "5.1.05",
        "Impostos sobre Receita",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.06.01.01.01",
        3,
    ),
    ItemPlano(
        "5.1.99",
        "Outras Despesas Operacionais — A Classificar",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.99.01.01.01",
        3,
    ),
)


# ── Mapas exportados — usados pelo motor automático (PR2) ───────────────────


CODIGOS_PADRAO_LANCAMENTO_AUTO: dict[str, str] = {
    # Mapeamento por evento → conta padrão
    "caixa": "1.1.1.01",
    "banco": "1.1.1.02",
    "clientes": "1.1.2.01",
    "fornecedores": "2.1.1.01",
    "receita_servicos": "4.1.01",
    "receita_vendas": "4.1.02",
    "outras_receitas": "4.9.99",
    "cmv": "5.1.01",
    "despesa_pessoal": "5.1.02",
    "encargos_sociais": "5.1.03",
    "despesa_depreciacao": "5.1.04",
    "outras_despesas": "5.1.99",
    "imobilizado": "1.2.3.01",
    "depreciacao_acumulada": "1.2.3.99",
    "provisao_ferias": "2.1.2.02",
    "provisao_13": "2.1.2.03",
    "inss_recolher": "2.1.3.01",
    "fgts_recolher": "2.1.3.02",
}
