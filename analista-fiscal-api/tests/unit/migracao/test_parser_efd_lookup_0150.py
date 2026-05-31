"""Testes do lookup CNPJ via 0150 — Sprint 19.7 PR3 (#36).

Cobre o helper compartilhado ``_extrair_mapa_participantes`` +
``parse_efd_contribuicoes`` + ``parse_efd_icms_ipi`` populando
``DocumentoFiscalImportado.cnpj_participante``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.migracao.parser_efd_contribuicoes import (
    _extrair_mapa_participantes,
    parse_efd_contribuicoes,
)
from app.modules.migracao.parser_efd_icms_ipi import parse_efd_icms_ipi
from app.modules.sped.efd.gerador_contribuicoes import (
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ParticipanteEfd,
    gerar_efd_contribuicoes,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ApuracaoMensalIcms,
    DocumentoIcmsEfd,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    ParticipanteIcms,
    gerar_efd_icms_ipi,
)


# ── _extrair_mapa_participantes ──────────────────────────────────────────


class TestExtrairMapaParticipantes:
    def test_mapa_basico_cnpj(self) -> None:
        linhas = [
            ["0150", "P001", "Acme LTDA", "01058", "11222333000144", "", "", "", "", "", "", ""],
            ["0150", "P002", "Fulano", "01058", "", "12345678900", "", "", "", "", "", ""],
        ]
        mapa = _extrair_mapa_participantes(linhas)
        assert mapa["P001"] == ("11222333000144", None)
        assert mapa["P002"] == (None, "12345678900")

    def test_mapa_vazio_quando_sem_0150(self) -> None:
        assert _extrair_mapa_participantes([["0000", "X"]]) == {}

    def test_cod_vazio_e_ignorado(self) -> None:
        linhas = [["0150", "", "Sem código", "01058", "11222333000144"]]
        assert _extrair_mapa_participantes(linhas) == {}


# ── parser EFD-Contribuições com lookup ──────────────────────────────────


def _empresa() -> IdentificacaoEmpresaEfd:
    return IdentificacaoEmpresaEfd(
        cnpj="11222333000144",
        razao_social="Empresa Demo LTDA",
        nome_fantasia=None,
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
    )


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


def test_parser_contribuicoes_resolve_cnpj_participante() -> None:
    participante = ParticipanteEfd(
        codigo="99887766000155",
        nome="Fornecedor X LTDA",
        cnpj="99887766000155",
    )
    doc = DocumentoMercadoriaEfd(
        chave="35250612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        modelo="55",
        data_emissao=date(2026, 4, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("1000"),
        valor_mercadorias=Decimal("1000"),
        valor_pis=Decimal("6.50"),
        valor_cofins=Decimal("30.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
        cfop="5102",
    )
    entrada = EntradaEfdContribuicoes(
        empresa=_empresa(),
        competencia_inicio=date(2026, 4, 1),
        competencia_fim=date(2026, 4, 30),
        apuracao=_ap(),
        participantes=(participante,),
        mercadorias=(doc,),
    )
    arquivo = gerar_efd_contribuicoes(entrada)
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    nfes = [d for d in parseado.documentos if d.tipo == "nfe"]
    assert len(nfes) == 1
    assert nfes[0].cnpj_participante == "99887766000155"
    assert nfes[0].cpf_participante is None


def test_parser_contribuicoes_participante_so_cpf_resolve_para_cpf() -> None:
    """Participante PF (só CPF, sem CNPJ) → cpf_participante populado."""
    participante = ParticipanteEfd(
        codigo="11122233344",
        nome="Cliente PF",
        cpf="11122233344",
    )
    doc = DocumentoMercadoriaEfd(
        chave="35250612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        modelo="55",
        data_emissao=date(2026, 4, 5),
        codigo_participante="11122233344",
        valor_total=Decimal("100"),
        valor_mercadorias=Decimal("100"),
        valor_pis=Decimal("0.65"),
        valor_cofins=Decimal("3.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
        cfop="5102",
    )
    entrada = EntradaEfdContribuicoes(
        empresa=_empresa(),
        competencia_inicio=date(2026, 4, 1),
        competencia_fim=date(2026, 4, 30),
        apuracao=_ap(),
        participantes=(participante,),
        mercadorias=(doc,),
    )
    arquivo = gerar_efd_contribuicoes(entrada)
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    nfes = [d for d in parseado.documentos if d.tipo == "nfe"]
    assert nfes[0].cnpj_participante is None
    assert nfes[0].cpf_participante == "11122233344"


# ── parser EFD ICMS-IPI com lookup ───────────────────────────────────────


def _empresa_icms() -> IdentificacaoEmpresaEfdIcms:
    return IdentificacaoEmpresaEfdIcms(
        cnpj="11222333000144",
        razao_social="Empresa Demo LTDA",
        nome_fantasia=None,
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        inscricao_estadual="111222333",
    )


def test_parser_icms_ipi_resolve_cnpj_participante() -> None:
    participante = ParticipanteIcms(
        codigo="99887766000155",
        nome="Fornecedor Y LTDA",
        cnpj="99887766000155",
    )
    doc = DocumentoIcmsEfd(
        chave="35250612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        modelo="55",
        data_emissao=date(2026, 4, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("1000"),
        valor_mercadorias=Decimal("1000"),
        valor_icms=Decimal("180"),
        aliquota_icms=Decimal("18"),
        cfop="5102",
    )
    entrada = EntradaEfdIcmsIpi(
        empresa=_empresa_icms(),
        competencia_inicio=date(2026, 4, 1),
        competencia_fim=date(2026, 4, 30),
        apuracao_icms=ApuracaoMensalIcms(
            valor_total_debitos=Decimal("180"),
            valor_total_creditos=Decimal("0"),
            saldo_credor_anterior=Decimal("0"),
            ajustes_devedores=Decimal("0"),
            ajustes_credores=Decimal("0"),
            valor_icms_a_recolher=Decimal("180"),
            saldo_credor_a_transportar=Decimal("0"),
        ),
        participantes=(participante,),
        documentos=(doc,),
    )
    arquivo = gerar_efd_icms_ipi(entrada)
    parseado = parse_efd_icms_ipi(arquivo.conteudo)
    nfes = [d for d in parseado.documentos if d.tipo == "nfe"]
    assert len(nfes) == 1
    assert nfes[0].cnpj_participante == "99887766000155"
