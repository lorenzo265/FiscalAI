"""Demonstração do Fluxo de Caixa — DFC método indireto.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 6.404/1976 art. 188 II (incluído pela Lei 11.638/2007) — DFC.
  * NBC TG 03 (R3) — alinhado a IAS 7.
  * CPC 03 (R2) — Demonstração dos Fluxos de Caixa.

Método aplicado: INDIRETO (mais usado e compatível com balancete).

Estrutura:

  ATIVIDADES OPERACIONAIS
    Lucro Líquido do Exercício
    (+) Itens não-caixa:
        + Depreciação / Amortização
        + Provisões (férias, 13º) constituídas
    (+) Variação no Capital de Giro:
        − Aumento de Clientes (aumento usa caixa)
        − Aumento de Estoques
        + Aumento de Fornecedores (libera caixa)
        + Aumento de Encargos a Pagar (idem)
    = Caixa Líquido das Atividades Operacionais

  ATIVIDADES DE INVESTIMENTO
    − Aquisição de Imobilizado
    + Venda de Imobilizado
    = Caixa Líquido das Atividades de Investimento

  ATIVIDADES DE FINANCIAMENTO
    + Aporte de Capital (variação positiva 3.1)
    + Empréstimos captados
    − Empréstimos pagos
    − Distribuição de Lucros
    = Caixa Líquido das Atividades de Financiamento

  VARIAÇÃO LÍQUIDA DO CAIXA = Op + Inv + Fin
  Saldo Inicial + Variação = Saldo Final (validação)

Para o MVP Sprint 12 PR2, modelamos os principais blocos. Caller passa as
variações já calculadas (delta = saldo_fim − saldo_inicio por conta). O
service abaixo deriva tudo de ``saldo_conta_mes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "dfc.indireto.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class EntradaDfc:
    """Variações + valores não-caixa do período.

    Convenção: cada campo é positivo quando representa o sentido natural
    (lucro positivo, depreciação positiva, aumento de clientes positivo).
    O algoritmo aplica o sinal correto ao agregar.
    """

    lucro_liquido: Decimal
    depreciacao_periodo: Decimal
    provisoes_constituidas: Decimal
    variacao_clientes: Decimal       # aumento positivo
    variacao_estoques: Decimal       # aumento positivo
    variacao_fornecedores: Decimal   # aumento positivo
    variacao_encargos_a_pagar: Decimal  # aumento positivo (INSS, FGTS, IRRF a recolher)
    aquisicao_imobilizado: Decimal   # positivo = aquisição
    venda_imobilizado: Decimal       # positivo = venda
    aporte_capital: Decimal          # positivo = aporte
    emprestimos_captados: Decimal    # positivo
    emprestimos_pagos: Decimal       # positivo
    distribuicao_lucros: Decimal     # positivo
    saldo_caixa_inicial: Decimal
    saldo_caixa_final: Decimal


@dataclass(frozen=True, slots=True)
class LinhaDfc:
    rotulo: str
    valor: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoDfc:
    """Snapshot persistido em ``relatorio_gerado.payload`` (tipo='dfc')."""

    lucro_liquido: LinhaDfc
    depreciacao: LinhaDfc
    provisoes: LinhaDfc
    variacao_clientes: LinhaDfc
    variacao_estoques: LinhaDfc
    variacao_fornecedores: LinhaDfc
    variacao_encargos: LinhaDfc
    caixa_operacional: LinhaDfc
    aquisicao_imobilizado: LinhaDfc
    venda_imobilizado: LinhaDfc
    caixa_investimento: LinhaDfc
    aporte_capital: LinhaDfc
    emprestimos_liquidos: LinhaDfc
    distribuicao_lucros: LinhaDfc
    caixa_financiamento: LinhaDfc
    variacao_liquida_caixa: LinhaDfc
    saldo_caixa_inicial: LinhaDfc
    saldo_caixa_final: LinhaDfc
    saldo_caixa_calculado: LinhaDfc  # inicial + variação líquida
    fecha: bool  # saldo_caixa_calculado == saldo_caixa_final ?
    diferenca: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_dfc(entrada: EntradaDfc) -> ResultadoDfc:
    """Calcula DFC método indireto.

    Args:
        entrada: variações + valores não-caixa + saldos de caixa do período.

    Returns:
        ResultadoDfc estruturado. ``fecha`` valida invariante:
        saldo_caixa_calculado == saldo_caixa_final.
    """
    # ── Operacional ─────────────────────────────────────────────────────
    op_total = (
        entrada.lucro_liquido
        + entrada.depreciacao_periodo
        + entrada.provisoes_constituidas
        - entrada.variacao_clientes        # aumento de clientes consome caixa
        - entrada.variacao_estoques
        + entrada.variacao_fornecedores    # aumento libera caixa
        + entrada.variacao_encargos_a_pagar
    )

    # ── Investimento ────────────────────────────────────────────────────
    inv_total = -entrada.aquisicao_imobilizado + entrada.venda_imobilizado

    # ── Financiamento ───────────────────────────────────────────────────
    emprestimos_liquidos = entrada.emprestimos_captados - entrada.emprestimos_pagos
    fin_total = (
        entrada.aporte_capital
        + emprestimos_liquidos
        - entrada.distribuicao_lucros
    )

    variacao_liquida = op_total + inv_total + fin_total
    saldo_calculado = entrada.saldo_caixa_inicial + variacao_liquida
    diferenca = _quantizar(saldo_calculado - entrada.saldo_caixa_final)
    fecha = diferenca == _ZERO

    return ResultadoDfc(
        lucro_liquido=LinhaDfc("Lucro Líquido do Exercício", _quantizar(entrada.lucro_liquido)),
        depreciacao=LinhaDfc("(+) Depreciação / Amortização", _quantizar(entrada.depreciacao_periodo)),
        provisoes=LinhaDfc("(+) Provisões Constituídas", _quantizar(entrada.provisoes_constituidas)),
        variacao_clientes=LinhaDfc(
            "(−) Aumento de Clientes", _quantizar(entrada.variacao_clientes),
        ),
        variacao_estoques=LinhaDfc(
            "(−) Aumento de Estoques", _quantizar(entrada.variacao_estoques),
        ),
        variacao_fornecedores=LinhaDfc(
            "(+) Aumento de Fornecedores", _quantizar(entrada.variacao_fornecedores),
        ),
        variacao_encargos=LinhaDfc(
            "(+) Aumento de Encargos a Pagar",
            _quantizar(entrada.variacao_encargos_a_pagar),
        ),
        caixa_operacional=LinhaDfc(
            "Caixa Líquido das Atividades Operacionais", _quantizar(op_total),
        ),
        aquisicao_imobilizado=LinhaDfc(
            "(−) Aquisição de Imobilizado",
            _quantizar(entrada.aquisicao_imobilizado),
        ),
        venda_imobilizado=LinhaDfc(
            "(+) Venda de Imobilizado", _quantizar(entrada.venda_imobilizado),
        ),
        caixa_investimento=LinhaDfc(
            "Caixa Líquido das Atividades de Investimento", _quantizar(inv_total),
        ),
        aporte_capital=LinhaDfc(
            "(+) Aporte de Capital", _quantizar(entrada.aporte_capital),
        ),
        emprestimos_liquidos=LinhaDfc(
            "(±) Empréstimos Líquidos (captação − pagamento)",
            _quantizar(emprestimos_liquidos),
        ),
        distribuicao_lucros=LinhaDfc(
            "(−) Distribuição de Lucros", _quantizar(entrada.distribuicao_lucros),
        ),
        caixa_financiamento=LinhaDfc(
            "Caixa Líquido das Atividades de Financiamento", _quantizar(fin_total),
        ),
        variacao_liquida_caixa=LinhaDfc(
            "Variação Líquida do Caixa", _quantizar(variacao_liquida),
        ),
        saldo_caixa_inicial=LinhaDfc(
            "Saldo de Caixa Inicial", _quantizar(entrada.saldo_caixa_inicial),
        ),
        saldo_caixa_final=LinhaDfc(
            "Saldo de Caixa Final (informado)",
            _quantizar(entrada.saldo_caixa_final),
        ),
        saldo_caixa_calculado=LinhaDfc(
            "Saldo de Caixa Calculado (inicial + variação)",
            _quantizar(saldo_calculado),
        ),
        fecha=fecha,
        diferenca=diferenca,
    )
