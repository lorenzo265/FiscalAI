"""Golden tests do Balanço Patrimonial (Sprint 12 PR2)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.relatorios.calcula_balanco import (
    ALGORITMO_VERSAO,
    SaldoConta,
    calcular_balanco,
)


def _s(codigo: str, valor: str, *, natureza: str = "D", tipo: str = "ativo") -> SaldoConta:
    return SaldoConta(
        codigo=codigo, descricao=codigo,
        natureza=natureza, tipo=tipo,
        saldo_final=Decimal(valor),
    )


class TestBalancoFechado:
    """Cenário canônico onde ATIVO = PASSIVO + PL."""

    def test_pequena_empresa_fechado(self) -> None:
        # ATIVO 50000
        #   Circ: caixa 10000 + clientes 15000 + estoques 5000 = 30000
        #   Não Circ: imobilizado 30000 − depreciação 10000 = 20000
        # PASSIVO+PL 50000
        #   Passivo Circ: fornec 8000 + INSS 2000 = 10000
        #   PL: capital 30000 + resultado 10000 = 40000
        saldos = [
            _s("1.1.1.01", "10000", tipo="ativo"),
            _s("1.1.2.01", "15000", tipo="ativo"),
            _s("1.1.3.01", "5000", tipo="ativo"),
            _s("1.2.3.01", "30000", tipo="ativo"),
            _s("1.2.3.99", "-10000", natureza="C", tipo="ativo"),
            _s("2.1.1.01", "8000", natureza="C", tipo="passivo"),
            _s("2.1.3.01", "2000", natureza="C", tipo="passivo"),
            _s("3.1.01", "30000", natureza="C", tipo="patrimonio_liquido"),
            _s("3.9.01", "10000", natureza="C", tipo="patrimonio_liquido"),
        ]
        r = calcular_balanco(saldos)
        assert r.ativo_circulante.valor == Decimal("30000.00")
        assert r.ativo_nao_circulante.valor == Decimal("20000.00")
        assert r.ativo_total.valor == Decimal("50000.00")
        assert r.passivo_circulante.valor == Decimal("10000.00")
        assert r.passivo_nao_circulante.valor == Decimal("0.00")
        assert r.patrimonio_liquido.valor == Decimal("40000.00")
        assert r.passivo_mais_pl_total.valor == Decimal("50000.00")
        assert r.fecha is True
        assert r.diferenca == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO


class TestBalancoNaoFechado:
    """Quando ATIVO ≠ PASSIVO + PL (típico antes do encerramento)."""

    def test_resultado_nao_encerrado_da_diferenca(self) -> None:
        # Capital 30000, Ativo 50000, Passivo 10000 → falta 10000 no PL
        # (provavelmente Resultado do Exercício não encerrado).
        saldos = [
            _s("1.1.1.01", "50000", tipo="ativo"),
            _s("2.1.1.01", "10000", natureza="C", tipo="passivo"),
            _s("3.1.01", "30000", natureza="C", tipo="patrimonio_liquido"),
        ]
        r = calcular_balanco(saldos)
        assert r.ativo_total.valor == Decimal("50000.00")
        assert r.passivo_mais_pl_total.valor == Decimal("40000.00")
        assert r.fecha is False
        assert r.diferenca == Decimal("10000.00")


class TestPassivoNaoCirculante:
    def test_emprestimo_lp_separado(self) -> None:
        # Empréstimo de longo prazo em 2.2.x — separa do circulante
        saldos = [
            _s("1.1.1.01", "20000", tipo="ativo"),
            _s("1.2.3.01", "80000", tipo="ativo"),
            _s("2.1.1.01", "10000", natureza="C", tipo="passivo"),
            _s("2.2.1.01", "50000", natureza="C", tipo="passivo"),  # LP
            _s("3.1.01", "40000", natureza="C", tipo="patrimonio_liquido"),
        ]
        r = calcular_balanco(saldos)
        assert r.passivo_circulante.valor == Decimal("10000.00")
        assert r.passivo_nao_circulante.valor == Decimal("50000.00")
        assert r.fecha is True


class TestDetalhamento:
    def test_contas_listadas_por_grupo(self) -> None:
        saldos = [
            _s("1.1.1.01", "5000", tipo="ativo"),
            _s("1.1.2.01", "3000", tipo="ativo"),
        ]
        r = calcular_balanco(saldos)
        assert len(r.ativo_circulante.contas) == 2
        codigos = {c[0] for c in r.ativo_circulante.contas}
        assert codigos == {"1.1.1.01", "1.1.2.01"}

    def test_zerados_filtrados(self) -> None:
        saldos = [
            _s("1.1.1.01", "5000", tipo="ativo"),
            _s("1.1.1.02", "0", tipo="ativo"),  # zerado → não aparece
        ]
        r = calcular_balanco(saldos)
        assert len(r.ativo_circulante.contas) == 1


class TestBordas:
    def test_sem_saldos(self) -> None:
        r = calcular_balanco([])
        assert r.ativo_total.valor == Decimal("0.00")
        assert r.passivo_mais_pl_total.valor == Decimal("0.00")
        assert r.fecha is True
        assert r.diferenca == Decimal("0.00")

    def test_match_prefixo_respeita_boundary(self) -> None:
        # "1.2" não deve casar com "1.20.x" (que não existe, mas defensivo)
        # E "2.1" não casa com "2.11.x" (boundary "."
        saldos = [
            _s("1.1.1.01", "10000", tipo="ativo"),
            _s("2.1.1.01", "10000", natureza="C", tipo="passivo"),
        ]
        r = calcular_balanco(saldos)
        assert r.ativo_total.valor == Decimal("10000.00")
        assert r.passivo_mais_pl_total.valor == Decimal("10000.00")
