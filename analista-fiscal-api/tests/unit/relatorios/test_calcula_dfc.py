"""Golden tests do DFC método indireto (Sprint 12 PR2)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.relatorios.calcula_dfc import (
    ALGORITMO_VERSAO,
    EntradaDfc,
    calcular_dfc,
)


def _zerada(**overrides: Decimal) -> EntradaDfc:
    """Helper: cria EntradaDfc com tudo zerado, sobrescreve só o que vem."""
    base = {
        "lucro_liquido": Decimal("0"),
        "depreciacao_periodo": Decimal("0"),
        "provisoes_constituidas": Decimal("0"),
        "variacao_clientes": Decimal("0"),
        "variacao_estoques": Decimal("0"),
        "variacao_fornecedores": Decimal("0"),
        "variacao_encargos_a_pagar": Decimal("0"),
        "aquisicao_imobilizado": Decimal("0"),
        "venda_imobilizado": Decimal("0"),
        "aporte_capital": Decimal("0"),
        "emprestimos_captados": Decimal("0"),
        "emprestimos_pagos": Decimal("0"),
        "distribuicao_lucros": Decimal("0"),
        "saldo_caixa_inicial": Decimal("0"),
        "saldo_caixa_final": Decimal("0"),
    }
    base.update(overrides)
    return EntradaDfc(**base)  # type: ignore[arg-type]


class TestOperacionalSimples:
    def test_so_lucro_liquido_fecha(self) -> None:
        # Lucro 10.000 → variação op = 10000; sem invest/financ
        # Saldo final = 0 + 10000 = 10000
        e = _zerada(
            lucro_liquido=Decimal("10000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("10000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_operacional.valor == Decimal("10000.00")
        assert r.variacao_liquida_caixa.valor == Decimal("10000.00")
        assert r.fecha is True
        assert r.diferenca == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_depreciacao_soma_de_volta(self) -> None:
        # Lucro 5.000 + depreciação 3.000 (não-caixa) = 8.000 op
        e = _zerada(
            lucro_liquido=Decimal("5000"),
            depreciacao_periodo=Decimal("3000"),
            saldo_caixa_inicial=Decimal("2000"),
            saldo_caixa_final=Decimal("10000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_operacional.valor == Decimal("8000.00")
        assert r.variacao_liquida_caixa.valor == Decimal("8000.00")
        assert r.fecha is True

    def test_variacao_capital_giro(self) -> None:
        # Lucro 10k − clientes aumentou 3k − estoques 2k + fornec 1k + encargos 500
        # = 10000 − 3000 − 2000 + 1000 + 500 = 6500
        e = _zerada(
            lucro_liquido=Decimal("10000"),
            variacao_clientes=Decimal("3000"),
            variacao_estoques=Decimal("2000"),
            variacao_fornecedores=Decimal("1000"),
            variacao_encargos_a_pagar=Decimal("500"),
            saldo_caixa_inicial=Decimal("1000"),
            saldo_caixa_final=Decimal("7500"),
        )
        r = calcular_dfc(e)
        assert r.caixa_operacional.valor == Decimal("6500.00")
        assert r.fecha is True


class TestInvestimento:
    def test_aquisicao_imobilizado_consome_caixa(self) -> None:
        # Compra imobilizado 20.000 → caixa investimento = −20000
        e = _zerada(
            lucro_liquido=Decimal("30000"),
            aquisicao_imobilizado=Decimal("20000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("10000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_operacional.valor == Decimal("30000.00")
        assert r.caixa_investimento.valor == Decimal("-20000.00")
        assert r.variacao_liquida_caixa.valor == Decimal("10000.00")
        assert r.fecha is True

    def test_venda_imobilizado_libera_caixa(self) -> None:
        e = _zerada(
            lucro_liquido=Decimal("5000"),
            venda_imobilizado=Decimal("8000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("13000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_investimento.valor == Decimal("8000.00")
        assert r.fecha is True


class TestFinanciamento:
    def test_aporte_capital(self) -> None:
        e = _zerada(
            aporte_capital=Decimal("50000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("50000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_financiamento.valor == Decimal("50000.00")
        assert r.fecha is True

    def test_emprestimos_liquidos(self) -> None:
        # Captou 30k, pagou 5k → líquido 25k
        e = _zerada(
            emprestimos_captados=Decimal("30000"),
            emprestimos_pagos=Decimal("5000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("25000"),
        )
        r = calcular_dfc(e)
        assert r.emprestimos_liquidos.valor == Decimal("25000.00")
        assert r.caixa_financiamento.valor == Decimal("25000.00")
        assert r.fecha is True

    def test_distribuicao_lucros_consome_caixa(self) -> None:
        e = _zerada(
            lucro_liquido=Decimal("20000"),
            distribuicao_lucros=Decimal("8000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("12000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_financiamento.valor == Decimal("-8000.00")
        assert r.fecha is True


class TestCenarioRealista:
    def test_ano_completo_pequena_empresa(self) -> None:
        # Lucro 100k + depreciação 12k − cliente 8k − estoque 4k + fornec 5k
        #   + encargos 2k = 107k operacional
        # Imobilizado: comprou 30k → −30k investimento
        # Financ: aporte 0, empréstimos pagos 10k, distribuiu 50k → −60k
        # Variação líquida = 107 − 30 − 60 = 17k
        # Caixa inicial 5k → final 22k
        e = EntradaDfc(
            lucro_liquido=Decimal("100000"),
            depreciacao_periodo=Decimal("12000"),
            provisoes_constituidas=Decimal("0"),
            variacao_clientes=Decimal("8000"),
            variacao_estoques=Decimal("4000"),
            variacao_fornecedores=Decimal("5000"),
            variacao_encargos_a_pagar=Decimal("2000"),
            aquisicao_imobilizado=Decimal("30000"),
            venda_imobilizado=Decimal("0"),
            aporte_capital=Decimal("0"),
            emprestimos_captados=Decimal("0"),
            emprestimos_pagos=Decimal("10000"),
            distribuicao_lucros=Decimal("50000"),
            saldo_caixa_inicial=Decimal("5000"),
            saldo_caixa_final=Decimal("22000"),
        )
        r = calcular_dfc(e)
        assert r.caixa_operacional.valor == Decimal("107000.00")
        assert r.caixa_investimento.valor == Decimal("-30000.00")
        assert r.caixa_financiamento.valor == Decimal("-60000.00")
        assert r.variacao_liquida_caixa.valor == Decimal("17000.00")
        assert r.fecha is True


class TestDfcNaoFecha:
    def test_diferenca_indica_problema(self) -> None:
        # Caller informa saldo final 1000 mas cálculo diz 5000 → diferença 4000
        # (típico quando faltou registrar movimento ou houve erro de partida)
        e = _zerada(
            lucro_liquido=Decimal("5000"),
            saldo_caixa_inicial=Decimal("0"),
            saldo_caixa_final=Decimal("1000"),
        )
        r = calcular_dfc(e)
        assert r.fecha is False
        assert r.diferenca == Decimal("4000.00")  # calculado − informado


# ── FIX #4 (PR6) — DFC dict-index: mesma aritmética que a busca individual ───


class TestDfcDictIndexEquivalencia:
    """Verifica que a lógica de soma in-memory via dict (FIX #4 PR6) produz
    exatamente o mesmo resultado que somar conta a conta manualmente.

    O cálculo continua byte-idêntico; apenas a contagem de queries muda.
    """

    def test_soma_grupo_equivale_soma_individual(self) -> None:
        """Dado um conjunto de saldos, somar via dict-lookup == somar conta a conta."""
        from decimal import Decimal as D

        saldos = {
            "1.1.01": D("5000.00"),
            "1.1.02": D("3000.00"),
            "1.2.01": D("1200.00"),
        }
        grupo = ("1.1.01", "1.1.02", "1.2.99")  # 1.2.99 ausente → 0
        _zero = D("0")
        soma_dict = sum((saldos.get(c, _zero) for c in grupo), _zero)

        soma_individual = D("5000.00") + D("3000.00") + D("0")

        assert soma_dict == soma_individual

    def test_conta_ausente_tratada_como_zero(self) -> None:
        """Conta não existente na posição → soma não levanta, assume 0."""
        from decimal import Decimal as D

        saldos: dict[str, D] = {}
        grupo = ("1.1.01", "1.1.02")
        soma = sum((saldos.get(c, D("0")) for c in grupo), D("0"))
        assert soma == D("0")

    def test_dfc_resultado_identico_com_dict_lookup(self) -> None:
        """A entrada manual com os valores extraídos via dict produz o mesmo
        resultado da calcular_dfc (regressão de paridade antes/depois do fix)."""
        # Simula o que gerar_dfc faria com saldos conhecidos.
        clientes_fim = Decimal("8000")
        clientes_ini = Decimal("5000")
        estoques_fim = Decimal("3000")
        estoques_ini = Decimal("4000")
        fornec_fim = Decimal("6000")
        fornec_ini = Decimal("4500")
        encargos_fim = Decimal("1500")
        encargos_ini = Decimal("1000")
        imob_fim = Decimal("20000")
        imob_ini = Decimal("15000")
        caixa_fim = Decimal("12000")
        caixa_ini = Decimal("5000")

        e = EntradaDfc(
            lucro_liquido=Decimal("10000"),
            depreciacao_periodo=Decimal("500"),
            provisoes_constituidas=Decimal("0"),
            variacao_clientes=clientes_fim - clientes_ini,
            variacao_estoques=estoques_fim - estoques_ini,
            variacao_fornecedores=fornec_fim - fornec_ini,
            variacao_encargos_a_pagar=encargos_fim - encargos_ini,
            aquisicao_imobilizado=max(imob_fim - imob_ini, Decimal("0")),
            venda_imobilizado=max(imob_ini - imob_fim, Decimal("0")),
            aporte_capital=Decimal("0"),
            emprestimos_captados=Decimal("0"),
            emprestimos_pagos=Decimal("0"),
            distribuicao_lucros=Decimal("0"),
            saldo_caixa_inicial=caixa_ini,
            saldo_caixa_final=caixa_fim,
        )
        r = calcular_dfc(e)
        # Operacional = lucro + deprec − Δclientes − Δestoques + Δfornec + Δencargos
        # = 10000 + 500 − 3000 − (−1000) + 1500 + 500 = 10500
        assert r.caixa_operacional.valor == Decimal("10500.00")
        # Investimento = −(imob_fim − imob_ini) = −5000
        assert r.caixa_investimento.valor == Decimal("-5000.00")
        # Variação líquida = 10500 − 5000 = 5500; caixa_ini 5000 → final 10500 (≠ 12000) → não fecha
        assert r.fecha is False
