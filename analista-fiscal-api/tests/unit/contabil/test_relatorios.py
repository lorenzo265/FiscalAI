"""Golden tests dos algoritmos puros de balancete e razão (Sprint 9 PR3)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.modules.contabil.relatorios import (
    LancamentoRazaoView,
    MovimentacaoConta,
    calcular_saldo_final,
    consolidar_balancete,
    consolidar_razao,
)


# ── calcular_saldo_final ────────────────────────────────────────────────────


class TestSaldoFinal:
    def test_natureza_d_debito_aumenta(self) -> None:
        # Ativo (D): saldo_inicial 100 + D 50 - C 30 = 120
        s = calcular_saldo_final(
            "D", Decimal("100"), Decimal("50"), Decimal("30")
        )
        assert s == Decimal("120")

    def test_natureza_d_credito_reduz(self) -> None:
        # Ativo (D): pagamento (C) reduz saldo
        s = calcular_saldo_final("D", Decimal("100"), Decimal("0"), Decimal("40"))
        assert s == Decimal("60")

    def test_natureza_c_credito_aumenta(self) -> None:
        # Passivo (C): saldo_inicial 100 + C 80 - D 30 = 150
        s = calcular_saldo_final(
            "C", Decimal("100"), Decimal("30"), Decimal("80")
        )
        assert s == Decimal("150")

    def test_natureza_c_debito_reduz(self) -> None:
        # Passivo (C): pagar dívida (D) reduz
        s = calcular_saldo_final(
            "C", Decimal("100"), Decimal("60"), Decimal("0")
        )
        assert s == Decimal("40")

    def test_saldo_pode_ficar_negativo(self) -> None:
        """Conta de ativo com saldo inicial 50 e crédito de 80 → -30."""
        s = calcular_saldo_final("D", Decimal("50"), Decimal("0"), Decimal("80"))
        assert s == Decimal("-30")

    def test_natureza_invalida_levanta(self) -> None:
        with pytest.raises(ValueError, match="natureza"):
            calcular_saldo_final("X", Decimal("0"), Decimal("0"), Decimal("0"))


# ── consolidar_balancete ────────────────────────────────────────────────────


def _mov(
    codigo: str = "1.1.1.01",
    natureza: str = "D",
    tipo: str = "ativo",
    saldo_inicial: str = "0",
    debitos: str = "0",
    creditos: str = "0",
) -> MovimentacaoConta:
    return MovimentacaoConta(
        conta_id=uuid.uuid4(),
        codigo=codigo,
        descricao=f"Conta {codigo}",
        natureza=natureza,
        tipo=tipo,
        nivel=4,
        saldo_inicial=Decimal(saldo_inicial),
        total_debitos=Decimal(debitos),
        total_creditos=Decimal(creditos),
    )


class TestConsolidarBalancete:
    def test_balancete_ordena_por_codigo(self) -> None:
        movs = [
            _mov(codigo="2.1.1.01"),
            _mov(codigo="1.1.1.01"),
            _mov(codigo="4.1.01"),
        ]
        linhas = consolidar_balancete(movs)
        codigos = [l.codigo for l in linhas]
        assert codigos == ["1.1.1.01", "2.1.1.01", "4.1.01"]

    def test_saldo_final_calculado_por_natureza(self) -> None:
        movs = [
            _mov(natureza="D", saldo_inicial="100", debitos="50", creditos="20"),
            _mov(codigo="2", natureza="C", saldo_inicial="200", debitos="50", creditos="30"),
        ]
        linhas = consolidar_balancete(movs)
        # Natureza D: 100 + 50 - 20 = 130
        assert linhas[0].saldo_final == Decimal("130")
        # Natureza C: 200 - 50 + 30 = 180
        assert linhas[1].saldo_final == Decimal("180")

    def test_balancete_vazio(self) -> None:
        assert consolidar_balancete([]) == []


# ── consolidar_razao ────────────────────────────────────────────────────────


def _lanc(
    tipo: str = "D",
    valor: str = "100",
    data: date = date(2026, 5, 10),
    historico: str = "x",
) -> LancamentoRazaoView:
    return LancamentoRazaoView(
        lancamento_id=uuid.uuid4(),
        data_lancamento=data,
        historico=historico,
        tipo=tipo,
        valor=Decimal(valor),
    )


class TestConsolidarRazao:
    def test_natureza_d_acumula_debitos(self) -> None:
        """Conta D: começou com 0, +100 D, +50 D → saldo 150."""
        lancs = [_lanc(tipo="D", valor="100"), _lanc(tipo="D", valor="50")]
        linhas = consolidar_razao("D", Decimal("0"), lancs)
        assert linhas[0].saldo_corrente == Decimal("100")
        assert linhas[1].saldo_corrente == Decimal("150")

    def test_natureza_d_credito_reduz(self) -> None:
        """Conta D: saldo 100, vem C 30 → saldo 70."""
        lancs = [_lanc(tipo="C", valor="30")]
        linhas = consolidar_razao("D", Decimal("100"), lancs)
        assert linhas[0].saldo_corrente == Decimal("70")
        assert linhas[0].debito == Decimal("0")
        assert linhas[0].credito == Decimal("30")

    def test_natureza_c_acumula_creditos(self) -> None:
        """Conta C: saldo 0, +200 C, +50 C → saldo 250."""
        lancs = [_lanc(tipo="C", valor="200"), _lanc(tipo="C", valor="50")]
        linhas = consolidar_razao("C", Decimal("0"), lancs)
        assert linhas[1].saldo_corrente == Decimal("250")

    def test_natureza_c_debito_reduz(self) -> None:
        """Conta C: saldo 200, vem D 80 → 120."""
        lancs = [_lanc(tipo="D", valor="80")]
        linhas = consolidar_razao("C", Decimal("200"), lancs)
        assert linhas[0].saldo_corrente == Decimal("120")

    def test_alternancia_d_c(self) -> None:
        """Conta D: 0, +D 100, +C 30, +D 50 → 120."""
        lancs = [
            _lanc(tipo="D", valor="100"),
            _lanc(tipo="C", valor="30"),
            _lanc(tipo="D", valor="50"),
        ]
        linhas = consolidar_razao("D", Decimal("0"), lancs)
        assert linhas[0].saldo_corrente == Decimal("100")
        assert linhas[1].saldo_corrente == Decimal("70")
        assert linhas[2].saldo_corrente == Decimal("120")

    def test_razao_vazio(self) -> None:
        """Lista vazia retorna lista vazia (saldo inicial preservado pelo caller)."""
        assert consolidar_razao("D", Decimal("100"), []) == []
