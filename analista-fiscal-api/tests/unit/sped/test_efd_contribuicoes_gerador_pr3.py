"""Testes do gerador EFD-Contribuições — Sprint 19.7 PR3 (#26 + #28).

Cobre:
  * #26 — granularidade item-a-item em C170 quando ``DocumentoMercadoriaEfd.itens``
    é populado.
  * #28 — retenção PJ→PJ na fonte: VL_PIS_RET/VL_COFINS_RET/VL_CSLL_RET reais
    no A100 (v1 emitia ``valor_total`` placeholder, valor inválido).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.sped.efd.gerador_contribuicoes import (
    ALGORITMO_VERSAO,
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    DocumentoServicoEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ItemMercadoriaEfd,
    ParticipanteEfd,
    _EntradaEfdInvalida,
    gerar_efd_contribuicoes,
)


def _empresa() -> IdentificacaoEmpresaEfd:
    return IdentificacaoEmpresaEfd(
        cnpj="12345678000190",
        razao_social="Comércio LTDA",
        nome_fantasia=None,
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
    )


def _participante() -> ParticipanteEfd:
    return ParticipanteEfd(codigo="99887766000155", nome="Cliente", cnpj="99887766000155")


def _ap() -> ApuracaoMensalPisCofins:
    return ApuracaoMensalPisCofins(
        base_calculo_pis=Decimal("0"),
        aliquota_pis=Decimal("0.65"),
        valor_pis_apurado=Decimal("0"),
        valor_pis_a_recolher=Decimal("0"),
        base_calculo_cofins=Decimal("0"),
        aliquota_cofins=Decimal("3.00"),
        valor_cofins_apurado=Decimal("0"),
        valor_cofins_a_recolher=Decimal("0"),
    )


def _entrada(
    *,
    servicos: tuple[DocumentoServicoEfd, ...] = (),
    mercadorias: tuple[DocumentoMercadoriaEfd, ...] = (),
) -> EntradaEfdContribuicoes:
    return EntradaEfdContribuicoes(
        empresa=_empresa(),
        competencia_inicio=date(2026, 4, 1),
        competencia_fim=date(2026, 4, 30),
        apuracao=_ap(),
        participantes=(_participante(),),
        servicos=servicos,
        mercadorias=mercadorias,
    )


# ── #26 — Granularidade item-a-item em C170 ──────────────────────────────


class TestGranularidadeItem:
    def test_emite_um_c170_por_item_quando_itens_populado(self) -> None:
        itens = (
            ItemMercadoriaEfd(
                n_item=1,
                codigo_produto="SKU-001",
                descricao="Camisa polo",
                quantidade=Decimal("10"),
                unidade="UN",
                valor_total=Decimal("3000.00"),
                valor_pis=Decimal("19.50"),
                valor_cofins=Decimal("90.00"),
                aliquota_pis=Decimal("0.65"),
                aliquota_cofins=Decimal("3.00"),
                cfop="5102",
                ncm="61051000",
            ),
            ItemMercadoriaEfd(
                n_item=2,
                codigo_produto="SKU-002",
                descricao="Calça jeans",
                quantidade=Decimal("5"),
                unidade="UN",
                valor_total=Decimal("2000.00"),
                valor_pis=Decimal("13.00"),
                valor_cofins=Decimal("60.00"),
                aliquota_pis=Decimal("0.65"),
                aliquota_cofins=Decimal("3.00"),
                cfop="6108",  # CFOP diferente do cabeçalho — interestadual
                ncm="62034210",
            ),
        )
        doc = DocumentoMercadoriaEfd(
            chave="35250612345678000190550010000010011000000010",
            numero="1001",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 4, 15),
            codigo_participante="99887766000155",
            valor_total=Decimal("5000.00"),
            valor_mercadorias=Decimal("5000.00"),
            valor_pis=Decimal("32.50"),
            valor_cofins=Decimal("150.00"),
            aliquota_pis=Decimal("0.65"),
            aliquota_cofins=Decimal("3.00"),
            cfop="5102",
            itens=itens,
        )
        out = gerar_efd_contribuicoes(_entrada(mercadorias=(doc,)))
        texto = out.conteudo.decode("latin-1")
        c170s = [ln for ln in texto.splitlines() if ln.startswith("|C170|")]
        assert len(c170s) == 2
        # Item 1 — CFOP 5102, SKU-001, NUM_ITEM=1.
        assert "|1|SKU-001|" in c170s[0]
        assert "|5102|" in c170s[0]
        # Item 2 — CFOP 6108, SKU-002, NUM_ITEM=2.
        assert "|2|SKU-002|" in c170s[1]
        assert "|6108|" in c170s[1]
        # Algoritmo bumpado pra v2.
        assert ALGORITMO_VERSAO == "sped.efd_contribuicoes.v3"

    def test_fallback_v1_quando_sem_itens(self) -> None:
        """Backward-compat — itens vazio mantém 'MERC-GENERICO' agregado."""
        doc = DocumentoMercadoriaEfd(
            chave="35250612345678000190550010000010021000000020",
            numero="1002",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 4, 16),
            codigo_participante="99887766000155",
            valor_total=Decimal("1000.00"),
            valor_mercadorias=Decimal("1000.00"),
            valor_pis=Decimal("6.50"),
            valor_cofins=Decimal("30.00"),
            aliquota_pis=Decimal("0.65"),
            aliquota_cofins=Decimal("3.00"),
            cfop="5102",
        )
        out = gerar_efd_contribuicoes(_entrada(mercadorias=(doc,)))
        texto = out.conteudo.decode("latin-1")
        c170s = [ln for ln in texto.splitlines() if ln.startswith("|C170|")]
        assert len(c170s) == 1
        assert "MERC-GENERICO" in c170s[0]

    def test_cfop_de_item_invalido_aborta(self) -> None:
        itens = (
            ItemMercadoriaEfd(
                n_item=1,
                codigo_produto="X",
                descricao="X",
                quantidade=Decimal("1"),
                unidade="UN",
                valor_total=Decimal("100"),
                valor_pis=Decimal("0"),
                valor_cofins=Decimal("0"),
                aliquota_pis=Decimal("0"),
                aliquota_cofins=Decimal("0"),
                cfop="ABCD",  # inválido
            ),
        )
        doc = DocumentoMercadoriaEfd(
            chave="35250612345678000190550010000010031000000030",
            numero="1003",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 4, 17),
            codigo_participante="99887766000155",
            valor_total=Decimal("100"),
            valor_mercadorias=Decimal("100"),
            valor_pis=Decimal("0"),
            valor_cofins=Decimal("0"),
            aliquota_pis=Decimal("0"),
            aliquota_cofins=Decimal("0"),
            cfop="5102",
            itens=itens,
        )
        with pytest.raises(_EntradaEfdInvalida, match="item 1"):
            gerar_efd_contribuicoes(_entrada(mercadorias=(doc,)))

    def test_item_com_quantidade_zero_aborta(self) -> None:
        itens = (
            ItemMercadoriaEfd(
                n_item=1,
                codigo_produto="X",
                descricao="X",
                quantidade=Decimal("0"),  # inválido
                unidade="UN",
                valor_total=Decimal("100"),
                valor_pis=Decimal("0"),
                valor_cofins=Decimal("0"),
                aliquota_pis=Decimal("0"),
                aliquota_cofins=Decimal("0"),
                cfop="5102",
            ),
        )
        doc = DocumentoMercadoriaEfd(
            chave="35250612345678000190550010000010041000000040",
            numero="1004",
            serie="1",
            modelo="55",
            data_emissao=date(2026, 4, 18),
            codigo_participante="99887766000155",
            valor_total=Decimal("100"),
            valor_mercadorias=Decimal("100"),
            valor_pis=Decimal("0"),
            valor_cofins=Decimal("0"),
            aliquota_pis=Decimal("0"),
            aliquota_cofins=Decimal("0"),
            cfop="5102",
            itens=itens,
        )
        with pytest.raises(_EntradaEfdInvalida, match="quantidade"):
            gerar_efd_contribuicoes(_entrada(mercadorias=(doc,)))


# ── #28 — Retenções PJ→PJ ────────────────────────────────────────────────


class TestRetencaoFonte:
    def test_vl_pis_ret_reflete_campo_e_nao_valor_total(self) -> None:
        """v2 emite valor_pis_retido_fonte; v1 emitia valor_total (bug)."""
        doc = DocumentoServicoEfd(
            chave=None,
            numero="100",
            serie="A",
            data_emissao=date(2026, 4, 20),
            codigo_participante="99887766000155",
            valor_total=Decimal("100000"),  # valor que era usado como placeholder
            valor_servicos=Decimal("100000"),
            valor_pis=Decimal("650.00"),
            valor_cofins=Decimal("3000.00"),
            aliquota_pis=Decimal("0.65"),
            aliquota_cofins=Decimal("3.00"),
            valor_pis_retido_fonte=Decimal("650.00"),
            valor_cofins_retido_fonte=Decimal("3000.00"),
            valor_csll_retido_fonte=Decimal("1000.00"),
        )
        out = gerar_efd_contribuicoes(_entrada(servicos=(doc,)))
        texto = out.conteudo.decode("latin-1")
        a100s = [ln for ln in texto.splitlines() if ln.startswith("|A100|")]
        assert len(a100s) == 1
        # Os 3 últimos campos antes do `|` final são VL_PIS_RET/COFINS_RET/CSLL_RET.
        # Formato SPED usa `,` como separador decimal.
        assert a100s[0].rstrip("|").endswith("|650,00|3000,00|1000,00")

    def test_default_retencao_zero_quando_omitida(self) -> None:
        """Backward-compat: sem retenção informada, emite 0 (não valor_total)."""
        doc = DocumentoServicoEfd(
            chave=None,
            numero="101",
            serie="A",
            data_emissao=date(2026, 4, 21),
            codigo_participante="99887766000155",
            valor_total=Decimal("50000"),
            valor_servicos=Decimal("50000"),
            valor_pis=Decimal("325.00"),
            valor_cofins=Decimal("1500.00"),
            aliquota_pis=Decimal("0.65"),
            aliquota_cofins=Decimal("3.00"),
            # sem campos de retenção — defaults Decimal('0')
        )
        out = gerar_efd_contribuicoes(_entrada(servicos=(doc,)))
        texto = out.conteudo.decode("latin-1")
        a100s = [ln for ln in texto.splitlines() if ln.startswith("|A100|")]
        # 3 valores de retenção = 0,00 ao final (antes do |).
        assert a100s[0].rstrip("|").endswith("|0,00|0,00|0,00")
