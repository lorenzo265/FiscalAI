"""Testes do parser EFD-Contribuições (Sprint 18 PR3).

Round-trip ``gerar_efd_contribuicoes → parse_efd_contribuicoes``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.migracao.parser_efd_contribuicoes import (
    ALGORITMO_VERSAO,
    EfdContribuicoesInvalida,
    parse_efd_contribuicoes,
)
from app.modules.sped.efd.gerador_contribuicoes import (
    ApuracaoMensalPisCofins,
    DocumentoMercadoriaEfd,
    DocumentoServicoEfd,
    EntradaEfdContribuicoes,
    IdentificacaoEmpresaEfd,
    ParticipanteEfd,
    gerar_efd_contribuicoes,
)


def _empresa() -> IdentificacaoEmpresaEfd:
    return IdentificacaoEmpresaEfd(
        cnpj="12345678000190",
        razao_social="Comercio Modelo LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="Sao Paulo",
        codigo_municipio_ibge="3550308",
    )


def _participante() -> ParticipanteEfd:
    return ParticipanteEfd(
        codigo="99887766000155",
        nome="Cliente Ficticio LTDA",
        cnpj="99887766000155",
    )


def _apuracao() -> ApuracaoMensalPisCofins:
    return ApuracaoMensalPisCofins(
        base_calculo_pis=Decimal("100000.00"),
        aliquota_pis=Decimal("0.65"),
        valor_pis_apurado=Decimal("650.00"),
        valor_pis_a_recolher=Decimal("650.00"),
        base_calculo_cofins=Decimal("100000.00"),
        aliquota_cofins=Decimal("3.00"),
        valor_cofins_apurado=Decimal("3000.00"),
        valor_cofins_a_recolher=Decimal("3000.00"),
    )


def _nfe() -> DocumentoMercadoriaEfd:
    return DocumentoMercadoriaEfd(
        chave="35250612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        modelo="55",
        data_emissao=date(2026, 3, 5),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_mercadorias=Decimal("50000.00"),
        valor_pis=Decimal("325.00"),
        valor_cofins=Decimal("1500.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
        cfop="5102",
        ncm="22030000",
    )


def _nfse() -> DocumentoServicoEfd:
    return DocumentoServicoEfd(
        chave=None,
        numero="42",
        serie="A",
        data_emissao=date(2026, 3, 10),
        codigo_participante="99887766000155",
        valor_total=Decimal("50000.00"),
        valor_servicos=Decimal("50000.00"),
        valor_pis=Decimal("325.00"),
        valor_cofins=Decimal("1500.00"),
        aliquota_pis=Decimal("0.65"),
        aliquota_cofins=Decimal("3.00"),
    )


def _entrada(
    *,
    servicos: tuple[DocumentoServicoEfd, ...] = (),
    mercadorias: tuple[DocumentoMercadoriaEfd, ...] = (),
) -> EntradaEfdContribuicoes:
    return EntradaEfdContribuicoes(
        empresa=_empresa(),
        competencia_inicio=date(2026, 3, 1),
        competencia_fim=date(2026, 3, 31),
        apuracao=_apuracao(),
        participantes=(_participante(),),
        servicos=servicos,
        mercadorias=mercadorias,
    )


def test_roundtrip_cabecalho() -> None:
    arquivo = gerar_efd_contribuicoes(_entrada(mercadorias=(_nfe(),)))
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    assert parseado.identificacao.cnpj == "12345678000190"
    assert parseado.identificacao.razao_social == "Comercio Modelo LTDA"
    assert parseado.identificacao.competencia_inicio == date(2026, 3, 1)
    assert parseado.identificacao.competencia_fim == date(2026, 3, 31)
    assert parseado.algoritmo_versao == ALGORITMO_VERSAO


def test_roundtrip_nfe_completa() -> None:
    arquivo = gerar_efd_contribuicoes(_entrada(mercadorias=(_nfe(),)))
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    docs_mercadoria = [d for d in parseado.documentos if d.tipo == "nfe"]
    assert len(docs_mercadoria) == 1
    doc = docs_mercadoria[0]
    assert doc.chave == "35250612345678000190550010000010011000000010"
    assert doc.numero == "1001"
    assert doc.serie == "1"
    assert doc.direcao == "saida"
    assert doc.valor_total == Decimal("50000.00")
    assert doc.valor_mercadorias == Decimal("50000.00")
    assert doc.cancelado is False
    assert len(doc.itens) == 1
    item = doc.itens[0]
    assert item.cfop == "5102"
    assert item.valor_pis == Decimal("325.00")
    assert item.valor_cofins == Decimal("1500.00")


def test_roundtrip_nfse() -> None:
    arquivo = gerar_efd_contribuicoes(_entrada(servicos=(_nfse(),)))
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    docs_servico = [d for d in parseado.documentos if d.tipo == "nfse"]
    assert len(docs_servico) == 1
    doc = docs_servico[0]
    assert doc.chave is None  # NFS-e sem chave ABRASF nesta fixture
    assert doc.numero == "42"
    assert doc.serie == "A"
    assert doc.valor_total == Decimal("50000.00")
    assert len(doc.itens) == 1
    assert doc.itens[0].valor_pis == Decimal("325.00")


def test_roundtrip_multiplos_documentos() -> None:
    arquivo = gerar_efd_contribuicoes(
        _entrada(
            servicos=(_nfse(),),
            mercadorias=(_nfe(), DocumentoMercadoriaEfd(
                chave="35250612345678000190550010000010021000000020",
                numero="1002", serie="1", modelo="55",
                data_emissao=date(2026, 3, 8),
                codigo_participante="99887766000155",
                valor_total=Decimal("25000.00"),
                valor_mercadorias=Decimal("25000.00"),
                valor_pis=Decimal("162.50"),
                valor_cofins=Decimal("750.00"),
                aliquota_pis=Decimal("0.65"),
                aliquota_cofins=Decimal("3.00"),
                cfop="5102",
            )),
        )
    )
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    assert len(parseado.documentos) == 3
    # Ordem: NFS-e primeiro (bloco A vem antes do C no gerador)
    tipos = [d.tipo for d in parseado.documentos]
    assert tipos == ["nfse", "nfe", "nfe"]


def test_apuracao_snapshot_preservada() -> None:
    arquivo = gerar_efd_contribuicoes(_entrada(mercadorias=(_nfe(),)))
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    # M200 grava VL_TOT_CONT_NC_PER no campo 2. Pode ser zero/valor — testamos só presença.
    assert "pis_apurado_periodo" in parseado.apuracao_snapshot
    assert "cofins_apurado_periodo" in parseado.apuracao_snapshot


def test_hash_estavel() -> None:
    arquivo = gerar_efd_contribuicoes(_entrada(mercadorias=(_nfe(),)))
    parseado = parse_efd_contribuicoes(arquivo.conteudo)
    assert parseado.hash_arquivo == arquivo.hash_sha256


def test_arquivo_vazio_levanta() -> None:
    with pytest.raises(EfdContribuicoesInvalida, match="vazio"):
        parse_efd_contribuicoes(b"")


def test_sem_0000_levanta() -> None:
    with pytest.raises(EfdContribuicoesInvalida, match="0000 ausente"):
        parse_efd_contribuicoes(b"|C001|0|\n|9999|2|\n")
