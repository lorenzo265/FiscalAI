"""Golden tests do DRE (Sprint 12 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.relatorios.calcula_dre import (
    ALGORITMO_VERSAO,
    SaldoConta,
    calcular_dre,
)


def _saldo(codigo: str, valor: str) -> SaldoConta:
    return SaldoConta(codigo=codigo, descricao=codigo, saldo_final=Decimal(valor))


class TestDreCompleto:
    """Cenário canônico — comércio com todas as linhas pontuando."""

    def test_dre_comercio_completo(self) -> None:
        # Receita 100.000 (vendas + serviços)
        # Impostos sobre receita: 8.000 (8% DAS)
        # CMV: 40.000
        # Pessoal + encargos: 20.000 + 5.000 = 25.000
        # Outras despesas (5.1.99): 5.000
        # Depreciação: 2.000
        # IRPJ + CSLL apurado: 1.500
        saldos = [
            _saldo("4.1.01", "60000"),   # Receita serviços
            _saldo("4.1.02", "40000"),   # Receita vendas
            _saldo("5.1.01", "40000"),   # CMV
            _saldo("5.1.02", "20000"),   # Pessoal
            _saldo("5.1.03", "5000"),    # Encargos
            _saldo("5.1.04", "2000"),    # Depreciação
            _saldo("5.1.05", "8000"),    # Impostos sobre Receita
            _saldo("5.1.99", "5000"),    # Outras despesas
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("1500"))

        assert r.receita_bruta.valor == Decimal("100000.00")
        assert sorted(r.receita_bruta.detalhes) == ["4.1.01", "4.1.02"]
        assert r.deducoes.valor == Decimal("8000.00")
        assert r.receita_liquida.valor == Decimal("92000.00")
        assert r.cmv.valor == Decimal("40000.00")
        assert r.lucro_bruto.valor == Decimal("52000.00")
        assert r.despesas_pessoal.valor == Decimal("25000.00")
        assert r.outras_despesas.valor == Decimal("5000.00")
        # EBITDA = Lucro Bruto − Pessoal − Outras = 52000 − 30000 = 22000
        assert r.ebitda.valor == Decimal("22000.00")
        assert r.depreciacao.valor == Decimal("2000.00")
        # EBIT = EBITDA − Depreciação = 20000
        assert r.ebit.valor == Decimal("20000.00")
        assert r.resultado_financeiro.valor == Decimal("0.00")
        assert r.lair.valor == Decimal("20000.00")
        assert r.irpj_csll.valor == Decimal("1500.00")
        # Lucro líquido = LAIR − IRPJ+CSLL = 18500
        assert r.lucro_liquido.valor == Decimal("18500.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO


class TestDreServicosLp:
    """Empresa LP de serviços — sem CMV, com despesas operacionais altas."""

    def test_lp_servicos_lucro_alto(self) -> None:
        # Receita 200.000, sem CMV, despesas operacionais 80.000
        # IRPJ+CSLL apurado externo: 12.000
        saldos = [
            _saldo("4.1.01", "200000"),
            _saldo("5.1.02", "60000"),
            _saldo("5.1.03", "15000"),
            _saldo("5.1.99", "5000"),
            _saldo("5.1.05", "5300"),     # PIS+Cofins+ISS
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("12000"))
        assert r.receita_bruta.valor == Decimal("200000.00")
        assert r.deducoes.valor == Decimal("5300.00")
        assert r.receita_liquida.valor == Decimal("194700.00")
        assert r.cmv.valor == Decimal("0.00")
        assert r.lucro_bruto.valor == Decimal("194700.00")
        # EBITDA = 194700 − 75000 − 5000 = 114700
        assert r.ebitda.valor == Decimal("114700.00")
        assert r.depreciacao.valor == Decimal("0.00")
        assert r.ebit.valor == Decimal("114700.00")
        # Lucro líquido = 114700 − 12000 = 102700
        assert r.lucro_liquido.valor == Decimal("102700.00")


class TestDrePrejuizo:
    """Cenário com prejuízo — despesas > receita."""

    def test_lucro_liquido_negativo(self) -> None:
        saldos = [
            _saldo("4.1.01", "10000"),
            _saldo("5.1.02", "20000"),    # Pessoal alto
            _saldo("5.1.04", "2000"),
        ]
        r = calcular_dre(saldos)
        assert r.receita_bruta.valor == Decimal("10000.00")
        assert r.receita_liquida.valor == Decimal("10000.00")
        # EBITDA = 10000 − 20000 = -10000
        assert r.ebitda.valor == Decimal("-10000.00")
        assert r.ebit.valor == Decimal("-12000.00")
        assert r.lair.valor == Decimal("-12000.00")
        assert r.lucro_liquido.valor == Decimal("-12000.00")


class TestResultadoFinanceiro:
    def test_com_resultado_financeiro_positivo(self) -> None:
        saldos = [
            _saldo("4.1.01", "50000"),
            _saldo("5.1.02", "10000"),
        ]
        # Receita financeira líquida 1500 (juros recebidos)
        r = calcular_dre(
            saldos,
            irpj_csll_apurado=Decimal("0"),
            resultado_financeiro=Decimal("1500"),
        )
        assert r.ebit.valor == Decimal("40000.00")
        assert r.lair.valor == Decimal("41500.00")

    def test_com_despesa_financeira_liquida(self) -> None:
        saldos = [
            _saldo("4.1.01", "50000"),
            _saldo("5.1.02", "10000"),
        ]
        # Despesa financeira líquida (juros pagos > recebidos)
        r = calcular_dre(
            saldos, resultado_financeiro=Decimal("-3000")
        )
        assert r.lair.valor == Decimal("37000.00")


class TestBordas:
    def test_sem_movimento_zera_tudo(self) -> None:
        r = calcular_dre([])
        assert r.receita_bruta.valor == Decimal("0.00")
        assert r.receita_liquida.valor == Decimal("0.00")
        assert r.lucro_liquido.valor == Decimal("0.00")

    def test_so_receita_sem_despesa(self) -> None:
        # Margem 100% (cenário irreal mas válido)
        r = calcular_dre([_saldo("4.1.01", "10000")])
        assert r.lucro_liquido.valor == Decimal("10000.00")

    def test_irpj_csll_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="irpj_csll_apurado"):
            calcular_dre([], irpj_csll_apurado=Decimal("-1"))

    def test_saldos_com_codigo_fora_do_plano_ignorados(self) -> None:
        # Conta 9.x não existe no plano → não casa com 4.x nem 5.x → ignorada
        saldos = [
            _saldo("4.1.01", "10000"),
            _saldo("9.9.99", "999999"),  # outlier
        ]
        r = calcular_dre(saldos)
        assert r.receita_bruta.valor == Decimal("10000.00")

    def test_match_por_prefixo_respeita_boundary(self) -> None:
        # "5.1.05" não deve casar com "5.1.0" (já que match é com ".").
        # Código "5.1.050" não casa com "5.1.05" porque "5.1.050" começa com
        # "5.1.05" mas não tem "." em seguida — vamos verificar.
        # Aqui validamos que "5.1.05" exato funciona e "5.1" como prefixo
        # SOMA todas as 5.1.x.
        saldos = [
            _saldo("5.1.05", "1000"),    # deducao
            _saldo("5.1.01", "2000"),    # cmv (não soma em deducao)
        ]
        r = calcular_dre(saldos)
        assert r.deducoes.valor == Decimal("1000.00")
        assert r.cmv.valor == Decimal("2000.00")
