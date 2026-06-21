"""Golden tests do DRE (Sprint 12 PR1 + FA6 M9 2026-06-04 + FA7 2026-06-21).

FA6: garante que 4.9.* (Outras Receitas) NÃO infla a ROB (Lei 6.404 art. 187).
FA7: garante que 5.2 (Despesas Financeiras) e 5.3 (Provisão IRPJ/CSLL) NÃO
     entram nas "Outras Despesas Operacionais" — eliminando dupla contagem
     (achado #5 auditoria 2026-06 — Lei 6.404/76 art. 187).
"""

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
        # FA6: sem 4.9.* → Outras Receitas = 0 (backward-compat)
        assert r.outras_receitas.valor == Decimal("0.00")
        assert r.outras_receitas.detalhes == ()
        assert r.resultado_financeiro.valor == Decimal("0.00")
        assert r.lair.valor == Decimal("20000.00")
        assert r.irpj_csll.valor == Decimal("1500.00")
        # Lucro líquido = LAIR − IRPJ+CSLL = 18500
        assert r.lucro_liquido.valor == Decimal("18500.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO
        assert ALGORITMO_VERSAO == "dre.estruturada.v3"


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


class TestFA6OutrasReceitas:
    """FA6 — M9 — 4.9.* NÃO compõe ROB (Lei 6.404 art. 187).

    Golden principal: DRE com saldo em 4.9.99 (Outras Receitas — A Classificar).

    Antes do fix: 4.9.99 infla ROB, Receita Líquida, todas as margens.
    Após o fix: ROB = apenas 4.1.*; 4.9.99 aparece como linha separada
    após EBIT; Lucro Líquido final é idêntico (a matemática fecha).
    """

    def test_rob_nao_inclui_outras_receitas(self) -> None:
        """Golden principal: 4.9.99 NÃO entra na ROB.

        Cenário numérico:
          Receita operacional (4.1.01)     = 80.000
          Outras Receitas     (4.9.99)     =  5.000  ← não-operacional
          Impostos sobre Rec  (5.1.05)     =  6.400  (8% do ROB)
          CMV                 (5.1.01)     = 30.000
          Pessoal             (5.1.02)     = 15.000
          Depreciação         (5.1.04)     =  2.000
          IRPJ+CSLL apurado               =  1.000

        ROB (correto)        = 80.000  (apenas 4.1.*)
        ROB (com bug antigo) = 85.000  (incluiria 4.9.99)
        Receita Líquida      = 80.000 − 6.400 = 73.600
        Lucro Bruto          = 73.600 − 30.000 = 43.600
        EBITDA               = 43.600 − 15.000 = 28.600
        EBIT                 = 28.600 −  2.000 = 26.600
        (+) Outras Receitas  =          5.000  ← entra aqui
        LAIR                 = 26.600 +  5.000 = 31.600
        IRPJ+CSLL            =          1.000
        Lucro Líquido        = 31.600 −  1.000 = 30.600
        """
        saldos = [
            _saldo("4.1.01", "80000"),   # Receita operacional
            _saldo("4.9.99", "5000"),    # Outras Receitas — A Classificar
            _saldo("5.1.01", "30000"),   # CMV
            _saldo("5.1.02", "15000"),   # Pessoal
            _saldo("5.1.04", "2000"),    # Depreciação
            _saldo("5.1.05", "6400"),    # Impostos sobre Receita
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("1000"))

        # ROB: APENAS 4.1.* — não inclui 4.9.99
        assert r.receita_bruta.valor == Decimal("80000.00"), (
            "ROB deve ser 80.000 (apenas 4.1.*), não 85.000 (bug M9)"
        )
        assert r.receita_bruta.detalhes == ("4.1.01",)

        # Deduções e Receita Líquida
        assert r.deducoes.valor == Decimal("6400.00")
        assert r.receita_liquida.valor == Decimal("73600.00")

        # Lucro Bruto
        assert r.cmv.valor == Decimal("30000.00")
        assert r.lucro_bruto.valor == Decimal("43600.00")

        # Despesas operacionais
        assert r.despesas_pessoal.valor == Decimal("15000.00")
        assert r.outras_despesas.valor == Decimal("0.00")  # nenhuma 5.1.99 aqui
        assert r.ebitda.valor == Decimal("28600.00")

        # EBIT
        assert r.depreciacao.valor == Decimal("2000.00")
        assert r.ebit.valor == Decimal("26600.00")

        # Outras Receitas — linha separada APÓS EBIT (Lei 6.404 art. 187)
        assert r.outras_receitas.valor == Decimal("5000.00"), (
            "4.9.99 deve aparecer como '(+) Outras Receitas' após EBIT"
        )
        assert "4.9.99" in r.outras_receitas.detalhes

        # LAIR soma EBIT + Outras Receitas + Resultado Financeiro
        assert r.resultado_financeiro.valor == Decimal("0.00")
        assert r.lair.valor == Decimal("31600.00")

        # Lucro Líquido
        assert r.irpj_csll.valor == Decimal("1000.00")
        assert r.lucro_liquido.valor == Decimal("30600.00")

    def test_backward_compat_sem_4_9(self) -> None:
        """DRE sem nenhuma conta 4.9.* → resultado idêntico ao pré-FA6.

        Prova que o fix não altera o comportamento quando 4.9.* é zero.
        """
        saldos = [
            _saldo("4.1.01", "50000"),
            _saldo("4.1.02", "30000"),
            _saldo("5.1.01", "20000"),
            _saldo("5.1.02", "10000"),
            _saldo("5.1.05", "6400"),
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("500"))

        # ROB = 4.1.01 + 4.1.02 = 80.000
        assert r.receita_bruta.valor == Decimal("80000.00")
        # Outras Receitas = 0 (sem 4.9.*)
        assert r.outras_receitas.valor == Decimal("0.00")
        assert r.outras_receitas.detalhes == ()
        # Receita Líquida = 80.000 − 6.400 = 73.600
        assert r.receita_liquida.valor == Decimal("73600.00")
        # Lucro Bruto = 73.600 − 20.000 = 53.600
        assert r.lucro_bruto.valor == Decimal("53600.00")
        # EBITDA = 53.600 − 10.000 = 43.600
        assert r.ebitda.valor == Decimal("43600.00")
        # EBIT = 43.600 (sem depreciação)
        assert r.ebit.valor == Decimal("43600.00")
        # LAIR = EBIT + 0 (Outras Receitas zero) = 43.600
        assert r.lair.valor == Decimal("43600.00")
        assert r.lucro_liquido.valor == Decimal("43100.00")

    def test_rob_antes_e_depois_do_fix_numérico(self) -> None:
        """Prova numérica explícita da diferença entre bug e fix.

        Com saldo 4.9.99 = 5.000 e 4.1.01 = 80.000:
          Bug (prefixo "4"): ROB = 85.000
          Fix (prefixo "4.1"): ROB = 80.000

        O lucro líquido FINAL deve ser o mesmo em ambos os mundos
        (o valor entra de qualquer jeito, só muda onde):
          Fix: EBIT 26.600 + OutrasRec 5.000 = LAIR 31.600 → LL 30.600
          Bug: teria ROB 85.000 → RL 78.600 → LB 48.600 → EBITDA 33.600
               → EBIT 31.600 → LAIR 31.600 → LL 30.600

        Observação: o LL final coincide apenas quando não há impostos sobre
        receita calculados sobre a diferença. O bug REAL é que ROB inflada
        distorce margens, carga tributária efetiva e Giro do Ativo.
        """
        saldos = [
            _saldo("4.1.01", "80000"),
            _saldo("4.9.99", "5000"),
            _saldo("5.1.04", "2000"),
            _saldo("5.1.02", "15000"),
        ]
        r = calcular_dre(saldos)

        # Fix: ROB = 80.000 (correto)
        assert r.receita_bruta.valor == Decimal("80000.00")
        # Fix: Outras Receitas isolada = 5.000
        assert r.outras_receitas.valor == Decimal("5000.00")
        # Fix: EBIT = 80000 - 15000 - 2000 = 63000
        assert r.ebit.valor == Decimal("63000.00")
        # Fix: LAIR = EBIT + Outras Receitas = 68.000
        assert r.lair.valor == Decimal("68000.00")
        assert r.lucro_liquido.valor == Decimal("68000.00")

    def test_outras_receitas_multiplas_subcontas(self) -> None:
        """4.9.x com múltiplas subcontas — todas capturadas em outras_receitas."""
        saldos = [
            _saldo("4.1.01", "100000"),
            _saldo("4.9.99", "3000"),    # Outras Receitas — A Classificar
            _saldo("4.9.01", "2000"),    # Hipotética subconta futura de 4.9
            _saldo("5.1.02", "20000"),
        ]
        r = calcular_dre(saldos)

        # ROB = apenas 4.1.* = 100.000
        assert r.receita_bruta.valor == Decimal("100000.00")
        # Outras Receitas = 4.9.99 + 4.9.01 = 5.000
        assert r.outras_receitas.valor == Decimal("5000.00")
        assert sorted(r.outras_receitas.detalhes) == ["4.9.01", "4.9.99"]
        # EBIT = 100000 − 20000 = 80000
        assert r.ebit.valor == Decimal("80000.00")
        # LAIR = 80000 + 5000 = 85000
        assert r.lair.valor == Decimal("85000.00")
        assert r.lucro_liquido.valor == Decimal("85000.00")


class TestFA7DuplasContagens:
    """FA7 — achado #5 — 5.2 e 5.3 fora das despesas operacionais.

    Lei 6.404/76 art. 187: resultado financeiro e provisão IRPJ/CSLL
    são linhas após o EBIT — não compõem o resultado operacional.

    Antes do fix: 5.2.01 e 5.3.01 eram capturados por _somar_prefixo("5",
    excluir=...) → entravam em 'Outras Despesas Operacionais' → EBITDA/EBIT
    contaminados → e depois o `resultado_financeiro` (parâmetro externo) e o
    `irpj_csll_apurado` eram somados/subtraídos de novo → DUPLA CONTAGEM.

    Após o fix: 5.2 e 5.3 excluídos das despesas operacionais → sem dupla
    contagem. 5.2 entra SOMENTE via `resultado_financeiro`; 5.3 entra SOMENTE
    via `irpj_csll_apurado`.
    """

    def test_5_2_nao_entra_nas_outras_despesas_operacionais(self) -> None:
        """Golden principal FA7: 5.2.01 NÃO contamina EBIT.

        Cenário numérico:
          Receita operacional  (4.1.01)  =  100.000
          Despesa pessoal      (5.1.02)  =   20.000
          Juros/desp.financ.   (5.2.01)  =    5.000  ← NÃO deve ir ao EBIT
          resultado_financeiro (externo) =   -5.000  ← entra só aqui

          EBIT correto   = 100.000 − 20.000 = 80.000
          EBIT com bug   = 100.000 − 20.000 − 5.000 = 75.000
          LAIR correto   = 80.000 + (-5.000) = 75.000
          LAIR com bug   = 75.000 + (-5.000) = 70.000  ← dupla contagem
          Lucro líquido  = LAIR (IRPJ/CSLL = 0)
        """
        saldos = [
            _saldo("4.1.01", "100000"),
            _saldo("5.1.02", "20000"),
            _saldo("5.2.01", "5000"),   # Juros e Encargos Financeiros
        ]
        r = calcular_dre(saldos, resultado_financeiro=Decimal("-5000"))

        # (a) EBIT/EBITDA NÃO incluem 5.2
        assert r.outras_despesas.valor == Decimal("0.00"), (
            "5.2.01 NÃO deve aparecer em Outras Despesas Operacionais"
        )
        assert "5.2.01" not in r.outras_despesas.detalhes
        assert r.ebitda.valor == Decimal("80000.00"), (
            "EBITDA = 100.000 - 20.000 = 80.000 (5.2 excluído)"
        )
        assert r.ebit.valor == Decimal("80000.00"), (
            "EBIT = 80.000 (sem depreciação, sem 5.2)"
        )

        # (b) resultado_financeiro entra UMA VEZ via parâmetro
        assert r.resultado_financeiro.valor == Decimal("-5000.00")

        # (c) lucro líquido fecha corretamente (sem dupla contagem)
        assert r.lair.valor == Decimal("75000.00"), (
            "LAIR = EBIT 80.000 + RF -5.000 = 75.000"
        )
        assert r.lucro_liquido.valor == Decimal("75000.00")

    def test_5_3_nao_entra_nas_outras_despesas_operacionais(self) -> None:
        """Golden FA7: 5.3.01 NÃO contamina EBIT.

        Cenário numérico:
          Receita operacional  (4.1.01)  =  100.000
          Despesa pessoal      (5.1.02)  =   20.000
          Provisão IRPJ/CSLL   (5.3.01)  =    8.000  ← NÃO deve ir ao EBIT
          irpj_csll_apurado  (externo)   =    8.000  ← entra só aqui

          EBIT correto  = 100.000 − 20.000 = 80.000
          EBIT com bug  = 100.000 − 20.000 − 8.000 = 72.000
          LAIR correto  = 80.000 (RF = 0)
          LL correto    = 80.000 − 8.000 = 72.000
          LL com bug    = 72.000 − 8.000 = 64.000  ← dupla contagem
        """
        saldos = [
            _saldo("4.1.01", "100000"),
            _saldo("5.1.02", "20000"),
            _saldo("5.3.01", "8000"),   # Provisão IRPJ / CSLL do Exercício
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("8000"))

        # (a) EBIT/EBITDA NÃO incluem 5.3
        assert r.outras_despesas.valor == Decimal("0.00"), (
            "5.3.01 NÃO deve aparecer em Outras Despesas Operacionais"
        )
        assert "5.3.01" not in r.outras_despesas.detalhes
        assert r.ebitda.valor == Decimal("80000.00"), (
            "EBITDA = 100.000 - 20.000 = 80.000 (5.3 excluído)"
        )
        assert r.ebit.valor == Decimal("80000.00")

        # (b) IRPJ/CSLL aparece UMA vez (via irpj_csll_apurado)
        assert r.irpj_csll.valor == Decimal("8000.00")

        # (c) lucro líquido fecha
        assert r.lair.valor == Decimal("80000.00")
        assert r.lucro_liquido.valor == Decimal("72000.00"), (
            "LL = LAIR 80.000 − IRPJ/CSLL 8.000 = 72.000 (sem dupla contagem)"
        )

    def test_5_2_e_5_3_simultaneos_sem_dupla_contagem(self) -> None:
        """Golden FA7 completo: 5.2 e 5.3 presentes juntos — zero dupla contagem.

        Cenário numérico (caso real LP com juros e provisão):
          Receita operacional  (4.1.01)  =  200.000
          Impostos sobre rec.  (5.1.05)  =   12.000
          CMV                  (5.1.01)  =   80.000
          Despesa pessoal      (5.1.02)  =   30.000
          Outras desp. oper.   (5.1.99)  =   10.000
          Depreciação          (5.1.04)  =    5.000
          ─────── EBIT ─── 200k-12k-80k-30k-10k-5k = 63.000
          Juros financ.        (5.2.01)  =    3.000  ← NÃO operacional
          resultado_financeiro (externo) =   -3.000
          ─────── LAIR ─── 63.000 + (-3.000) = 60.000
          Provisão IRPJ/CSLL   (5.3.01)  =    9.000  ← NÃO operacional
          irpj_csll_apurado  (externo)   =    9.000
          ─────── LL ─── 60.000 − 9.000 = 51.000

        Com bug antigo:
          outras_despesas = 10.000 + 3.000 + 9.000 = 22.000
          EBITDA = 200k-12k-80k-30k-22k = 56k; EBIT = 51k
          LAIR = 51k + (-3k) = 48k; LL = 48k - 9k = 39k  ← ERRADO
        """
        saldos = [
            _saldo("4.1.01", "200000"),
            _saldo("5.1.01", "80000"),
            _saldo("5.1.02", "30000"),
            _saldo("5.1.04", "5000"),
            _saldo("5.1.05", "12000"),
            _saldo("5.1.99", "10000"),
            _saldo("5.2.01", "3000"),   # Juros — deve ser excluído do operacional
            _saldo("5.3.01", "9000"),   # Provisão IR — deve ser excluído do operacional
        ]
        r = calcular_dre(
            saldos,
            irpj_csll_apurado=Decimal("9000"),
            resultado_financeiro=Decimal("-3000"),
        )

        # Receita
        assert r.receita_bruta.valor == Decimal("200000.00")
        assert r.deducoes.valor == Decimal("12000.00")
        assert r.receita_liquida.valor == Decimal("188000.00")
        assert r.cmv.valor == Decimal("80000.00")
        assert r.lucro_bruto.valor == Decimal("108000.00")

        # Despesas operacionais — APENAS 5.1.99 (NÃO inclui 5.2/5.3)
        assert r.despesas_pessoal.valor == Decimal("30000.00")
        assert r.outras_despesas.valor == Decimal("10000.00"), (
            "5.1.99 = 10.000; 5.2.01 e 5.3.01 NÃO devem estar aqui"
        )
        assert "5.2.01" not in r.outras_despesas.detalhes
        assert "5.3.01" not in r.outras_despesas.detalhes

        # (a) EBIT sem 5.2/5.3
        assert r.ebitda.valor == Decimal("68000.00"), (
            "EBITDA = 108.000 - 30.000 - 10.000 = 68.000"
        )
        assert r.depreciacao.valor == Decimal("5000.00")
        assert r.ebit.valor == Decimal("63000.00"), (
            "EBIT = 68.000 - 5.000 = 63.000"
        )

        # (b) resultado financeiro UMA VEZ
        assert r.resultado_financeiro.valor == Decimal("-3000.00")
        assert r.lair.valor == Decimal("60000.00")

        # (b) IRPJ/CSLL UMA VEZ
        assert r.irpj_csll.valor == Decimal("9000.00")

        # (c) lucro líquido fecha
        assert r.lucro_liquido.valor == Decimal("51000.00"), (
            "LL = LAIR 60.000 − IRPJ/CSLL 9.000 = 51.000 (zero dupla contagem)"
        )

    def test_5_2_subcontas_multiplas_excluidas(self) -> None:
        """Todas subcontas de 5.2 excluídas pelo prefixo boundary.

        5.2.01 e hipotética 5.2.02 devem ambas ser excluídas.
        """
        saldos = [
            _saldo("4.1.01", "50000"),
            _saldo("5.1.02", "10000"),
            _saldo("5.2.01", "2000"),   # Juros
            _saldo("5.2.02", "500"),    # Hipotética taxa bancária
        ]
        r = calcular_dre(saldos, resultado_financeiro=Decimal("-2500"))

        assert r.outras_despesas.valor == Decimal("0.00")
        assert "5.2.01" not in r.outras_despesas.detalhes
        assert "5.2.02" not in r.outras_despesas.detalhes
        assert r.ebit.valor == Decimal("40000.00")
        assert r.lair.valor == Decimal("37500.00")

    def test_backward_compat_sem_5_2_e_5_3(self) -> None:
        """Sem saldos em 5.2/5.3: comportamento idêntico ao pré-FA7.

        Prova que o fix não altera resultados quando as contas financeiras
        e de provisão têm saldo zero (empresa sem juros/LP, SN sem IRPJ/CSLL).
        """
        saldos = [
            _saldo("4.1.01", "80000"),
            _saldo("5.1.01", "30000"),
            _saldo("5.1.02", "15000"),
            _saldo("5.1.05", "6400"),
        ]
        r = calcular_dre(saldos, irpj_csll_apurado=Decimal("1000"))

        assert r.receita_bruta.valor == Decimal("80000.00")
        assert r.deducoes.valor == Decimal("6400.00")
        assert r.receita_liquida.valor == Decimal("73600.00")
        assert r.lucro_bruto.valor == Decimal("43600.00")
        assert r.despesas_pessoal.valor == Decimal("15000.00")
        assert r.outras_despesas.valor == Decimal("0.00")
        assert r.ebitda.valor == Decimal("28600.00")
        assert r.ebit.valor == Decimal("28600.00")
        assert r.lair.valor == Decimal("28600.00")
        assert r.irpj_csll.valor == Decimal("1000.00")
        assert r.lucro_liquido.valor == Decimal("27600.00")
