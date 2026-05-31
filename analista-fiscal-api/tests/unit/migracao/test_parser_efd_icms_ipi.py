"""Testes do parser EFD ICMS-IPI (Sprint 18 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.migracao.parser_efd_icms_ipi import (
    ALGORITMO_VERSAO,
    EfdIcmsIpiInvalida,
    parse_efd_icms_ipi,
)
from app.modules.sped.efd.gerador_icms_ipi import (
    ApuracaoMensalIcms,
    ApuracaoMensalIpi,
    DocumentoIcmsEfd,
    EntradaEfdIcmsIpi,
    IdentificacaoEmpresaEfdIcms,
    ObrigacaoIcmsRecolher,
    ParticipanteIcms,
    gerar_efd_icms_ipi,
)


def _empresa() -> IdentificacaoEmpresaEfdIcms:
    return IdentificacaoEmpresaEfdIcms(
        cnpj="12345678000190",
        razao_social="Comercio SP LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="Sao Paulo",
        codigo_municipio_ibge="3550308",
        inscricao_estadual="111222333",
    )


def _apuracao() -> ApuracaoMensalIcms:
    return ApuracaoMensalIcms(
        valor_total_debitos=Decimal("9000.00"),
        valor_total_creditos=Decimal("0"),
        saldo_credor_anterior=Decimal("0"),
        ajustes_devedores=Decimal("0"),
        ajustes_credores=Decimal("0"),
        valor_icms_a_recolher=Decimal("9000.00"),
        saldo_credor_a_transportar=Decimal("0"),
    )


def _nfe() -> DocumentoIcmsEfd:
    return DocumentoIcmsEfd(
        chave="35260612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        modelo="55",
        data_emissao=date(2026, 3, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_mercadorias=Decimal("50000.00"),
        valor_icms=Decimal("9000.00"),
        aliquota_icms=Decimal("18.00"),
        cfop="5102",
        cst_icms="000",
        ncm="22030000",
    )


def _entrada(docs: tuple[DocumentoIcmsEfd, ...] = ()) -> EntradaEfdIcmsIpi:
    return EntradaEfdIcmsIpi(
        empresa=_empresa(),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao_icms=_apuracao(),
        participantes=(
            ParticipanteIcms(
                codigo="99887766000155",
                nome="Cliente",
                cnpj="99887766000155",
            ),
        ),
        documentos=docs,
        obrigacoes_a_recolher=(
            ObrigacaoIcmsRecolher(
                codigo_obrigacao="000",
                valor=Decimal("9000.00"),
                data_vencimento=date(2026, 4, 10),
            ),
        ),
        apuracao_ipi=ApuracaoMensalIpi(preenchido=False),
    )


def test_roundtrip_cabecalho() -> None:
    arquivo = gerar_efd_icms_ipi(_entrada(docs=(_nfe(),)))
    parseado = parse_efd_icms_ipi(arquivo.conteudo)
    assert parseado.identificacao.cnpj == "12345678000190"
    assert parseado.identificacao.uf == "SP"
    assert parseado.identificacao.inscricao_estadual == "111222333"
    assert parseado.identificacao.competencia_inicio == date(2026, 3, 1)
    assert parseado.algoritmo_versao == ALGORITMO_VERSAO


def test_roundtrip_nfe_com_icms() -> None:
    arquivo = gerar_efd_icms_ipi(_entrada(docs=(_nfe(),)))
    parseado = parse_efd_icms_ipi(arquivo.conteudo)
    assert len(parseado.documentos) == 1
    doc = parseado.documentos[0]
    assert doc.tipo == "nfe"
    assert doc.chave == "35260612345678000190550010000010011000000010"
    assert doc.valor_total == Decimal("50000.00")
    assert doc.cfop == "5102"  # promovido do C170 ao cabeçalho
    assert len(doc.itens) == 1
    item = doc.itens[0]
    assert item.cst_icms == "000"
    assert item.cfop == "5102"
    assert item.valor_icms == Decimal("9000.00")


def test_apuracao_icms_snapshot() -> None:
    arquivo = gerar_efd_icms_ipi(_entrada(docs=(_nfe(),)))
    parseado = parse_efd_icms_ipi(arquivo.conteudo)
    snap = parseado.apuracao_icms_snapshot
    # Os valores são serializados como strings de Decimal SPED (1234,56).
    assert "icms_total_debitos" in snap
    assert "icms_a_recolher" in snap
    assert snap["icms_a_recolher"] == "9000,00"


def test_hash_estavel() -> None:
    arquivo = gerar_efd_icms_ipi(_entrada(docs=(_nfe(),)))
    parseado = parse_efd_icms_ipi(arquivo.conteudo)
    assert parseado.hash_arquivo == arquivo.hash_sha256


def test_arquivo_vazio_levanta() -> None:
    with pytest.raises(EfdIcmsIpiInvalida, match="vazio"):
        parse_efd_icms_ipi(b"")


def test_sem_0000_levanta() -> None:
    with pytest.raises(EfdIcmsIpiInvalida, match="0000 ausente"):
        parse_efd_icms_ipi(b"|C001|0|\n|9999|2|\n")
