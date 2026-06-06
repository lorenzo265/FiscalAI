"""Plano de contas referencial mínimo brasileiro (Sprint 9 PR1).

Inspirado no Plano de Contas Referencial PJ da Receita Federal (publicado no
SPED ECD). Contas sintéticas + analíticas cobrindo o MVP:

* Ativo circulante (caixa, banco, clientes, estoque).
* Ativo não-circulante (imobilizado + depreciação acumulada).
* Passivo circulante (fornecedores, salários, INSS, FGTS, provisões trabalhistas,
  impostos a recolher: ICMS, ISS, PIS, Cofins, IRPJ, CSLL).
* Passivo não-circulante (empréstimos e financiamentos LP).
* PL (capital, lucros acumulados, resultado do exercício, lucros distribuídos).
* Receitas (vendas serviços, vendas mercadorias, deduções da receita bruta,
  receitas financeiras).
* Despesas (CMV, salários, encargos, depreciação, impostos, despesas financeiras,
  provisão IRPJ/CSLL).

Cada item: ``(codigo, descricao, parent_codigo, natureza, tipo, aceita_lancamento, codigo_ecd)``.

O motor de lançamentos automáticos (PR2) usa códigos específicos como
"1.1.1.02" (banco) ou "4.1.01.01" (CMV) — manter chaves estáveis.

⚠ PENDÊNCIA: empresas já existentes (criadas antes desta revisão) não recebem
as novas contas retroativamente — backfill via migration dedicada fica como
follow-up (clonar-padrão cobre apenas novas empresas).
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
    # Sprint 19.7 PR1 (#10) — IRRF retido na folha. Subconta de Encargos a
    # Recolher (2.1.3.x) ao invés de Impostos (2.1.4.x) pra manter a
    # contrapartida da folha agrupada (consistente com INSS/FGTS).
    ItemPlano(
        "2.1.3.03",
        "IRRF Funcionários a Recolher",
        "2.1.3",
        "C",
        "passivo",
        True,
        "2.01.03.03.01.01",
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
    # Impostos separados por tributo (Lucro Presumido / regimes específicos).
    # ECD RFB: grupo 2.01.04 — Impostos e Contribuições a Recolher.
    ItemPlano(
        "2.1.4.02",
        "ICMS a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.01.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4.03",
        "ISS a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.02.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4.04",
        "PIS a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.03.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4.05",
        "COFINS a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.04.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4.06",
        "IRPJ a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.05.01.01",
        4,
    ),
    ItemPlano(
        "2.1.4.07",
        "CSLL a Recolher",
        "2.1.4",
        "C",
        "passivo",
        True,
        "2.01.04.06.01.01",
        4,
    ),
    # ── 2.2 PASSIVO NÃO CIRCULANTE ─────────────────────────────────────────
    # ECD RFB: 2.02 Passivo Não Circulante.
    ItemPlano(
        "2.2", "PASSIVO NÃO CIRCULANTE", "2", "C", "passivo", False, "2.02", 2
    ),
    ItemPlano(
        "2.2.1",
        "Empréstimos e Financiamentos",
        "2.2",
        "C",
        "passivo",
        False,
        "2.02.01",
        3,
    ),
    ItemPlano(
        "2.2.1.01",
        "Empréstimos e Financiamentos a Longo Prazo",
        "2.2.1",
        "C",
        "passivo",
        True,
        "2.02.01.01.01.01",
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
    # Lucros distribuídos: natureza D (redutora do PL) — ECD RFB 3.07.02.
    ItemPlano(
        "3.9.02",
        "Lucros Distribuídos",
        "3.9",
        "D",
        "patrimonio_liquido",
        True,
        "3.07.02.01.01.01",
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
    # Deduções da Receita Bruta — natureza D (retificadora), tipo receita.
    # Lei 6.404/76 art. 187 I: ROB → (-) devoluções/abatimentos/cancelamentos
    # → Receita Líquida. ECD RFB: 4.01.03 Deduções da Receita Bruta.
    ItemPlano(
        "4.1.03",
        "(-) Deduções da Receita Bruta",
        "4.1",
        "D",
        "receita",
        True,
        "4.01.03.01.01.01",
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
    # Receitas Financeiras — ECD RFB: 4.01.02 Receitas Financeiras.
    ItemPlano(
        "4.9.01",
        "Receitas Financeiras",
        "4.9",
        "C",
        "receita",
        True,
        "4.01.02.01.01.01",
        3,
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
        "5.1.06",
        "Serviços de Terceiros",
        "5.1",
        "D",
        "despesa",
        True,
        "4.02.07.01.01.01",
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
    # ── 5.2 DESPESAS FINANCEIRAS ────────────────────────────────────────────
    # ECD RFB: 4.03 Despesas Financeiras (fora do resultado operacional).
    ItemPlano(
        "5.2",
        "Despesas Financeiras",
        "5",
        "D",
        "despesa",
        False,
        "4.03",
        2,
    ),
    ItemPlano(
        "5.2.01",
        "Juros e Encargos Financeiros",
        "5.2",
        "D",
        "despesa",
        True,
        "4.03.01.01.01.01",
        3,
    ),
    # ── 5.3 PROVISÃO IRPJ / CSLL (resultado antes do lucro líquido) ─────────
    # Lei 6.404/76 art. 189 + IN RFB: provisão de IRPJ e CSLL é dedução do
    # resultado, fora do lucro operacional. ECD RFB: 4.05 IRPJ / CSLL Diferidos
    # (grupo correto para lucro presumido / real). Coloca-se fora de 5.1
    # (operacional) para manter DRE conforme art. 187.
    ItemPlano(
        "5.3",
        "Provisão para IRPJ e CSLL",
        "5",
        "D",
        "despesa",
        False,
        "4.05",
        2,
    ),
    ItemPlano(
        "5.3.01",
        "Provisão IRPJ / CSLL do Exercício",
        "5.3",
        "D",
        "despesa",
        True,
        "4.05.01.01.01.01",
        3,
    ),
)


# ── Mapas exportados — usados pelo motor automático (PR2) ───────────────────


CODIGOS_PADRAO_LANCAMENTO_AUTO: dict[str, str] = {
    # Mapeamento por evento → conta padrão.
    # ⚠ Fonte canônica única — sempre que o DFC, encerramento, lançador auto
    # ou qualquer relatório precisar de um código de conta, leia daqui.
    "caixa": "1.1.1.01",
    "banco": "1.1.1.02",
    "clientes": "1.1.2.01",
    "estoques": "1.1.3.01",
    "fornecedores": "2.1.1.01",
    "salarios_pagar": "2.1.2.01",
    "receita_servicos": "4.1.01",
    "receita_vendas": "4.1.02",
    "outras_receitas": "4.9.99",
    "cmv": "5.1.01",
    "despesa_pessoal": "5.1.02",
    "encargos_sociais": "5.1.03",
    "despesa_depreciacao": "5.1.04",
    "despesa_servicos": "5.1.06",
    "outras_despesas": "5.1.99",
    "imobilizado": "1.2.3.01",
    "depreciacao_acumulada": "1.2.3.99",
    "provisao_ferias": "2.1.2.02",
    "provisao_13": "2.1.2.03",
    "inss_recolher": "2.1.3.01",
    "fgts_recolher": "2.1.3.02",
    # Sprint 19.7 PR1 (#10) — IRRF retido na folha (contrapartida do desconto).
    "irrf_funcionarios_recolher": "2.1.3.03",
    # DAS Simples Nacional a Recolher.
    "das_recolher": "2.1.4.01",
    # Impostos a Recolher por tributo (Lucro Presumido / regimes específicos).
    "icms_recolher": "2.1.4.02",
    "iss_recolher": "2.1.4.03",
    "pis_recolher": "2.1.4.04",
    "cofins_recolher": "2.1.4.05",
    "irpj_recolher": "2.1.4.06",
    "csll_recolher": "2.1.4.07",
    # Despesa de imposto sobre receita (DAS / ICMS / ISS / PIS / Cofins).
    "impostos_sobre_receita": "5.1.05",
    # Provisão IRPJ / CSLL do exercício.
    "provisao_irpj_csll": "5.3.01",
    # Passivo Não-Circulante.
    "emprestimos_lp": "2.2.1.01",
    # PL — Lucros Distribuídos.
    "lucros_distribuidos": "3.9.02",
    # Receitas — Deduções da Receita Bruta (retificadora).
    "deducoes_receita": "4.1.03",
    # Resultado Financeiro.
    "receitas_financeiras": "4.9.01",
    "despesas_financeiras": "5.2.01",
}

# ── Conjuntos de chaves por contexto ────────────────────────────────────────
# _CHAVES_CORE: as 20 chaves usadas pelo motor automático de lançamentos
# (nfe/transacao/depreciacao/provisao/folha). Iteradas explicitamente em
# resolver_contas() para que novas entradas no dict (icms_recolher etc.)
# nunca quebrem empresas que clonaram o plano antes de sua criação.
_CHAVES_CORE: tuple[str, ...] = (
    "clientes",
    "fornecedores",
    "banco",
    "receita_servicos",
    "receita_vendas",
    "outras_receitas",
    "outras_despesas",
    "despesa_depreciacao",
    "depreciacao_acumulada",
    "despesa_pessoal",
    "encargos_sociais",
    "provisao_ferias",
    "provisao_13",
    "inss_recolher",
    "fgts_recolher",
    "irrf_funcionarios_recolher",
    "salarios_pagar",
    "estoques",
    "imobilizado",
    "despesa_servicos",
)

# _CHAVES_IMPOSTOS: chaves resolvidas exclusivamente para lote_impostos().
# Ausência de qualquer uma destas NÃO quebra os outros lotes.
_CHAVES_IMPOSTOS: tuple[str, ...] = (
    "das_recolher",
    "icms_recolher",
    "iss_recolher",
    "pis_recolher",
    "cofins_recolher",
    "irpj_recolher",
    "csll_recolher",
    "impostos_sobre_receita",
    "provisao_irpj_csll",
)


def codigo(chave: str) -> str:
    """Retorna o código contábil para uma chave simbólica.

    Falha rápido (KeyError) se a chave não estiver mapeada — evita typo
    silencioso virar saldo zero no relatório.
    """
    return CODIGOS_PADRAO_LANCAMENTO_AUTO[chave]


# Agrupamentos para consumidores (DFC, indicadores, etc.).
# Lista de chaves simbólicas — o consumidor resolve via `codigo()`.
GRUPOS_CONTABEIS: dict[str, tuple[str, ...]] = {
    # DFC — caixa equivalentes (1.1.1.x)
    "caixa_equivalentes": ("caixa", "banco"),
    # DFC — capital de giro
    "clientes": ("clientes",),
    "estoques": ("estoques",),
    "fornecedores": ("fornecedores",),
    # DFC — "Encargos a Pagar" = salários + INSS + FGTS a recolher
    "encargos_a_pagar": ("salarios_pagar", "inss_recolher", "fgts_recolher"),
    # DFC — Imobilizado bruto (sem depreciação acumulada — vai à parte)
    "imobilizado_bruto": ("imobilizado",),
}


def codigos_do_grupo(grupo: str) -> tuple[str, ...]:
    """Retorna a tupla de códigos contábeis de um grupo simbólico."""
    return tuple(codigo(k) for k in GRUPOS_CONTABEIS[grupo])
