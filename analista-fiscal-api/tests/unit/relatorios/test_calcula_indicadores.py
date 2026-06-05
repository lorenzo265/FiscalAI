"""Golden tests dos Indicadores financeiros (Sprint 12 PR3)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.relatorios.calcula_balanco import (
    LinhaBalanco,
    ResultadoBalanco,
)
from app.modules.relatorios.calcula_dre import (
    LinhaDre,
    ResultadoDre,
)
from app.modules.relatorios.calcula_indicadores import (
    ALGORITMO_VERSAO,
    calcular_indicadores,
)


def _balanco(
    ac: str = "0",
    anc: str = "0",
    pc: str = "0",
    pnc: str = "0",
    pl: str = "0",
    contas_ac: tuple[tuple[str, str, Decimal], ...] = (),
) -> ResultadoBalanco:
    ativo_circ = LinhaBalanco("Ativo Circulante", Decimal(ac), contas_ac)
    ativo_nao_circ = LinhaBalanco("Ativo Não Circulante", Decimal(anc))
    return ResultadoBalanco(
        ativo_circulante=ativo_circ,
        ativo_nao_circulante=ativo_nao_circ,
        ativo_total=LinhaBalanco("ATIVO", Decimal(ac) + Decimal(anc)),
        passivo_circulante=LinhaBalanco("PC", Decimal(pc)),
        passivo_nao_circulante=LinhaBalanco("PNC", Decimal(pnc)),
        patrimonio_liquido=LinhaBalanco("PL", Decimal(pl)),
        passivo_mais_pl_total=LinhaBalanco(
            "P+PL", Decimal(pc) + Decimal(pnc) + Decimal(pl)
        ),
        fecha=True,
        diferenca=Decimal("0"),
    )


def _dre(
    receita_liquida: str = "0",
    lucro_bruto: str = "0",
    ebitda: str = "0",
    lucro_liquido: str = "0",
) -> ResultadoDre:
    zero = LinhaDre("zero", Decimal("0"))
    return ResultadoDre(
        receita_bruta=zero,
        deducoes=zero,
        receita_liquida=LinhaDre("RL", Decimal(receita_liquida)),
        cmv=zero,
        lucro_bruto=LinhaDre("LB", Decimal(lucro_bruto)),
        despesas_pessoal=zero,
        outras_despesas=zero,
        ebitda=LinhaDre("EBITDA", Decimal(ebitda)),
        depreciacao=zero,
        ebit=zero,
        outras_receitas=zero,  # FA6 — campo obrigatório novo (4.9.*)
        resultado_financeiro=zero,
        lair=zero,
        irpj_csll=zero,
        lucro_liquido=LinhaDre("LL", Decimal(lucro_liquido)),
    )


class TestLiquidez:
    def test_liquidez_corrente_saudavel(self) -> None:
        # AC 50.000 / PC 25.000 = 2,0000 (saudável >1)
        b = _balanco(ac="50000", pc="25000")
        d = _dre()
        r = calcular_indicadores(b, d)
        assert r.liquidez_corrente.valor == Decimal("2.0000")
        assert r.liquidez_corrente.formato == "razao"

    def test_liquidez_corrente_apertada(self) -> None:
        # AC 30k / PC 40k = 0,7500 (apertada <1)
        r = calcular_indicadores(_balanco(ac="30000", pc="40000"), _dre())
        assert r.liquidez_corrente.valor == Decimal("0.7500")

    def test_liquidez_seca_remove_estoques(self) -> None:
        # AC 50k inclui 10k estoque (1.1.3.01); LS = 40k/25k = 1,6
        b = _balanco(
            ac="50000", pc="25000",
            contas_ac=(("1.1.3.01", "Mercadorias", Decimal("10000")),),
        )
        r = calcular_indicadores(b, _dre())
        assert r.liquidez_seca.valor == Decimal("1.6000")

    def test_pc_zero_retorna_none(self) -> None:
        r = calcular_indicadores(_balanco(ac="50000", pc="0"), _dre())
        assert r.liquidez_corrente.valor is None

    def test_liquidez_geral(self) -> None:
        # (AC + ANC) / (PC + PNC) = 100k / 40k = 2,5
        b = _balanco(ac="60000", anc="40000", pc="30000", pnc="10000")
        r = calcular_indicadores(b, _dre())
        assert r.liquidez_geral.valor == Decimal("2.5000")


class TestEstruturaCapital:
    def test_endividamento_geral(self) -> None:
        # Passivo 40k / Ativo 100k = 0,4000 (40%)
        b = _balanco(ac="60000", anc="40000", pc="30000", pnc="10000", pl="60000")
        r = calcular_indicadores(b, _dre())
        assert r.endividamento_geral.valor == Decimal("0.4000")

    def test_composicao_endividamento(self) -> None:
        # PC 30k / Passivo 40k = 0,7500 (75% no curto prazo)
        b = _balanco(ac="60000", anc="40000", pc="30000", pnc="10000")
        r = calcular_indicadores(b, _dre())
        assert r.composicao_endividamento.valor == Decimal("0.7500")


class TestRentabilidade:
    def test_margens(self) -> None:
        # Receita líquida 100k, Lucro bruto 60k, EBITDA 30k, Lucro líquido 18k
        d = _dre(
            receita_liquida="100000",
            lucro_bruto="60000",
            ebitda="30000",
            lucro_liquido="18000",
        )
        b = _balanco()
        r = calcular_indicadores(b, d)
        assert r.margem_bruta.valor == Decimal("0.6000")
        assert r.margem_ebitda.valor == Decimal("0.3000")
        assert r.margem_liquida.valor == Decimal("0.1800")

    def test_roa_e_roe(self) -> None:
        # LL 20k, Ativo 200k → ROA = 0,1 (10%)
        # PL 100k → ROE = 0,2 (20%)
        b = _balanco(ac="120000", anc="80000", pl="100000")
        d = _dre(receita_liquida="0", lucro_liquido="20000")
        r = calcular_indicadores(b, d)
        assert r.roa.valor == Decimal("0.1000")
        assert r.roe.valor == Decimal("0.2000")

    def test_giro_ativo(self) -> None:
        # Receita 300k / Ativo 100k = 3,0
        b = _balanco(ac="60000", anc="40000")
        d = _dre(receita_liquida="300000")
        r = calcular_indicadores(b, d)
        assert r.giro_ativo.valor == Decimal("3.0000")

    def test_receita_zero_margens_none(self) -> None:
        r = calcular_indicadores(_balanco(), _dre())
        assert r.margem_bruta.valor is None
        assert r.margem_liquida.valor is None
        assert r.giro_ativo.valor is None

    def test_pl_zero_roe_none(self) -> None:
        # PL zero = empresa nova sem aporte ainda
        b = _balanco(ac="50000", pl="0")
        d = _dre(lucro_liquido="10000")
        r = calcular_indicadores(b, d)
        assert r.roe.valor is None


class TestEstrutura:
    def test_algoritmo_versao(self) -> None:
        r = calcular_indicadores(_balanco(), _dre())
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_11_indicadores_estruturados(self) -> None:
        r = calcular_indicadores(_balanco(), _dre())
        # Smoke test estrutural
        assert r.liquidez_corrente.formato in ("razao", "percentual")
        assert r.margem_bruta.formato == "percentual"
        assert r.giro_ativo.formato == "razao"
