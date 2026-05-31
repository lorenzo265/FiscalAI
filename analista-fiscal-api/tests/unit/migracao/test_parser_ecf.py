"""Testes do parser SPED ECF — snapshot read-only (Sprint 18 PR2).

Round-trip ``gerar_ecf → parse_ecf`` valida que extraímos as apurações
trimestrais declaradas pelo escritório antigo (IRPJ + CSLL) sem perda.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.migracao.parser_ecf import (
    ALGORITMO_VERSAO,
    EcfInvalido,
    parse_ecf,
)
from app.modules.sped.ecf.gerador import (
    ApuracaoTrimestralLp,
    ContaPlanoEcf,
    EntradaEcf,
    IdentificacaoEmpresaEcf,
    InformacoesGerais,
    SaldoContaTrimestre,
    gerar_ecf,
)


def _empresa() -> IdentificacaoEmpresaEcf:
    return IdentificacaoEmpresaEcf(
        cnpj="12345678000190",
        razao_social="Comercio Modelo LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="Sao Paulo",
        codigo_municipio_ibge="3550308",
    )


def _plano() -> tuple[ContaPlanoEcf, ...]:
    return (
        ContaPlanoEcf(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlanoEcf(
            codigo="4.1.01", descricao="Receita Servicos", natureza="C", nivel=3,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
    )


def _apuracao_trimestre(numero: int, receita: str = "100000.00") -> ApuracaoTrimestralLp:
    inicio = date(2025, 3 * (numero - 1) + 1, 1)
    mes_fim = 3 * (numero - 1) + 3
    if mes_fim == 12:
        fim = date(2025, 12, 31)
    else:
        fim = date(2025, mes_fim + 1, 1) - timedelta(days=1)
    rec = Decimal(receita)
    pres = Decimal("0.3200")
    base = rec * pres
    irpj = base * Decimal("0.15")
    csll = base * Decimal("0.09")
    return ApuracaoTrimestralLp(
        inicio=inicio,
        fim=fim,
        numero_trimestre=numero,
        receita_bruta=rec,
        percentual_presuncao_irpj=pres,
        percentual_presuncao_csll=pres,
        base_presumida_irpj=base,
        base_presumida_csll=base,
        ganhos_capital=Decimal("0"),
        receitas_aplicacoes=Decimal("0"),
        outras_adicoes_irpj=Decimal("0"),
        outras_adicoes_csll=Decimal("0"),
        base_total_irpj=base,
        base_total_csll=base,
        limite_adicional_irpj=Decimal("60000.00"),
        irpj_normal=irpj,
        irpj_adicional=Decimal("0"),
        irpj_total=irpj,
        irrf_a_compensar=Decimal("0"),
        irrf_consumido=Decimal("0"),
        irpj_devido=irpj,
        csll_devida=csll,
    )


def _entrada(num_trimestres: int = 4) -> EntradaEcf:
    return EntradaEcf(
        empresa=_empresa(),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        forma_tributacao="4",
        ecd_vinculada=None,
        plano_contas=_plano(),
        saldos_por_trimestre=(
            (1, (
                SaldoContaTrimestre(
                    codigo_conta="1.1.1.01",
                    saldo_inicial=Decimal("0"),
                    indicador_saldo_inicial="D",
                    debitos=Decimal("100000.00"),
                    creditos=Decimal("0"),
                    saldo_final=Decimal("100000.00"),
                    indicador_saldo_final="D",
                ),
            )),
        ),
        apuracoes_trimestrais=tuple(
            _apuracao_trimestre(n) for n in range(1, num_trimestres + 1)
        ),
        informacoes_gerais=InformacoesGerais(
            discriminacao_receita=(("01", Decimal("400000.00")),),
            socios=(),
        ),
    )


def test_roundtrip_cabecalho() -> None:
    arquivo = gerar_ecf(_entrada())
    parseado = parse_ecf(arquivo.conteudo)
    assert parseado.identificacao.cnpj == "12345678000190"
    assert parseado.identificacao.razao_social == "Comercio Modelo LTDA"
    assert parseado.identificacao.inicio_exercicio == date(2025, 1, 1)
    assert parseado.identificacao.fim_exercicio == date(2025, 12, 31)
    assert parseado.identificacao.forma_tributacao == "4"  # LP
    assert parseado.algoritmo_versao == ALGORITMO_VERSAO


def test_roundtrip_4_trimestres() -> None:
    arquivo = gerar_ecf(_entrada(num_trimestres=4))
    parseado = parse_ecf(arquivo.conteudo)
    assert len(parseado.apuracoes_trimestrais) == 4
    inicios = [ap.inicio for ap in parseado.apuracoes_trimestrais]
    assert inicios == [
        date(2025, 1, 1),
        date(2025, 4, 1),
        date(2025, 7, 1),
        date(2025, 10, 1),
    ]


def test_roundtrip_valores_irpj() -> None:
    """IRPJ normal = base × 15%. Receita 100k × 32% × 15% = 4800."""
    arquivo = gerar_ecf(_entrada(num_trimestres=1))
    parseado = parse_ecf(arquivo.conteudo)
    ap = parseado.apuracoes_trimestrais[0]
    assert ap.receita_bruta == Decimal("100000.00")
    assert ap.base_total_irpj == Decimal("32000.00")
    assert ap.irpj_normal == Decimal("4800.00")
    assert ap.irpj_total == Decimal("4800.00")
    assert ap.irpj_devido == Decimal("4800.00")


def test_roundtrip_valores_csll() -> None:
    """CSLL = base × 9%. Receita 100k × 32% × 9% = 2880."""
    arquivo = gerar_ecf(_entrada(num_trimestres=1))
    parseado = parse_ecf(arquivo.conteudo)
    ap = parseado.apuracoes_trimestrais[0]
    assert ap.base_total_csll == Decimal("32000.00")
    assert ap.csll_devida == Decimal("2880.00")


def test_hash_estavel_round_trip() -> None:
    arquivo = gerar_ecf(_entrada())
    parseado = parse_ecf(arquivo.conteudo)
    assert parseado.hash_arquivo == arquivo.hash_sha256


def test_blocos_brutos_inclui_p_e_y() -> None:
    """Counter de blocos cobre os registros principais — sanidade."""
    arquivo = gerar_ecf(_entrada())
    parseado = parse_ecf(arquivo.conteudo)
    assert parseado.blocos_brutos.get("0000", 0) == 1
    assert parseado.blocos_brutos.get("P010", 0) == 4
    assert parseado.blocos_brutos.get("P200", 0) == 4
    assert parseado.blocos_brutos.get("P300", 0) == 4
    assert parseado.blocos_brutos.get("9999", 0) == 1


def test_arquivo_vazio_levanta() -> None:
    with pytest.raises(EcfInvalido, match="vazio"):
        parse_ecf(b"")


def test_arquivo_sem_0000_levanta() -> None:
    with pytest.raises(EcfInvalido, match="0000 ausente"):
        parse_ecf(b"|P001|0|\n|9999|2|\n")
