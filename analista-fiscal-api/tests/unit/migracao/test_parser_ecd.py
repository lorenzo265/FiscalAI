"""Testes do parser SPED ECD (Sprint 18 PR2).

Estratégia: usa o gerador da Sprint 16 PR1 como produtor de fixture e
verifica que o parser reverte os dados sem perda — golden round-trip
``gerar_ecd → parse_ecd``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.migracao.parser_ecd import (
    ALGORITMO_VERSAO,
    EcdInvalido,
    parse_ecd,
)
from app.modules.sped.ecd.gerador import (
    ContaPlano,
    EntradaEcd,
    IdentificacaoEmpresaEcd,
    LancamentoEcd,
    LinhaDemonstracao,
    PartidaLanc,
    SaldoPeriodico,
    SaldoPeriodicoConta,
    SaldoResultadoConta,
    gerar_ecd,
)


# ── Fixtures (reusam padrão do test_ecd_gerador) ────────────────────────────


def _empresa() -> IdentificacaoEmpresaEcd:
    return IdentificacaoEmpresaEcd(
        cnpj="12345678000190",
        razao_social="Comercio Modelo LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="Sao Paulo",
        codigo_municipio_ibge="3550308",
    )


def _plano_minimo() -> tuple[ContaPlano, ...]:
    return (
        ContaPlano(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai="1.1",
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlano(
            codigo="4.1.01", descricao="Receita de Servicos", natureza="C",
            nivel=3, tipo_conta="A", codigo_pai="4",
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
    )


def _lanc(numero: str, dia: int, valor: str) -> LancamentoEcd:
    return LancamentoEcd(
        numero=numero,
        data=date(2025, 3, dia),
        valor_total=Decimal(valor),
        indicador_origem="N",
        partidas=(
            PartidaLanc(
                codigo_conta="1.1.1.01",
                valor=Decimal(valor),
                indicador_dc="D",
                historico="Recebimento servico",
            ),
            PartidaLanc(
                codigo_conta="4.1.01",
                valor=Decimal(valor),
                indicador_dc="C",
                historico="Recebimento servico",
            ),
        ),
    )


def _entrada_minima(
    lancamentos: tuple[LancamentoEcd, ...] | None = None,
) -> EntradaEcd:
    if lancamentos is None:
        lancamentos = (_lanc("1", 15, "1000.00"),)
    return EntradaEcd(
        empresa=_empresa(),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        plano_contas=_plano_minimo(),
        saldos_periodicos=(
            SaldoPeriodico(
                inicio=date(2025, 3, 1),
                fim=date(2025, 3, 31),
                saldos=(
                    SaldoPeriodicoConta(
                        codigo_conta="1.1.1.01",
                        saldo_inicial=Decimal("0"),
                        indicador_saldo_inicial="D",
                        total_debitos=Decimal("1000.00"),
                        total_creditos=Decimal("0"),
                        saldo_final=Decimal("1000.00"),
                        indicador_saldo_final="D",
                    ),
                ),
            ),
        ),
        lancamentos=lancamentos,
        saldos_resultado_antes_encerramento=(
            SaldoResultadoConta(
                codigo_conta="4.1.01",
                valor=Decimal("1000.00"),
                indicador_dc="C",
            ),
        ),
        balanco=(
            LinhaDemonstracao("1", 1, "D", "ATIVO", Decimal("1000.00")),
        ),
        dre=(
            LinhaDemonstracao("3.01", 2, "C", "Receita", Decimal("1000.00")),
        ),
    )


# ── Round-trip ──────────────────────────────────────────────────────────────


def test_roundtrip_cabecalho() -> None:
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    assert parseado.identificacao.cnpj == "12345678000190"
    assert parseado.identificacao.razao_social == "Comercio Modelo LTDA"
    assert parseado.identificacao.uf == "SP"
    assert parseado.identificacao.codigo_municipio_ibge == "3550308"
    assert parseado.identificacao.inicio_exercicio == date(2025, 1, 1)
    assert parseado.identificacao.fim_exercicio == date(2025, 12, 31)
    assert parseado.identificacao.leiaute_versao == "10.00"
    assert parseado.algoritmo_versao == ALGORITMO_VERSAO


def test_roundtrip_plano_contas() -> None:
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    codigos = [c.codigo for c in parseado.plano_contas]
    assert "1.1.1.01" in codigos
    assert "4.1.01" in codigos
    caixa = next(c for c in parseado.plano_contas if c.codigo == "1.1.1.01")
    assert caixa.descricao == "Caixa"
    assert caixa.natureza == "D"
    assert caixa.tipo_conta == "A"
    assert caixa.nivel == 4
    assert caixa.codigo_pai == "1.1"


def test_roundtrip_lancamento_simples() -> None:
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    assert len(parseado.lancamentos) == 1
    lanc = parseado.lancamentos[0]
    assert lanc.numero == "1"
    assert lanc.data == date(2025, 3, 15)
    assert lanc.valor_total == Decimal("1000.00")
    assert lanc.indicador_origem == "N"
    assert len(lanc.partidas) == 2
    debito = next(p for p in lanc.partidas if p.indicador_dc == "D")
    credito = next(p for p in lanc.partidas if p.indicador_dc == "C")
    assert debito.codigo_conta == "1.1.1.01"
    assert debito.valor == Decimal("1000.00")
    assert credito.codigo_conta == "4.1.01"
    assert credito.valor == Decimal("1000.00")


def test_roundtrip_multiplos_lancamentos() -> None:
    lancs = (
        _lanc("1", 5, "100.00"),
        _lanc("2", 15, "250.50"),
        _lanc("3", 28, "999.99"),
    )
    arquivo = gerar_ecd(_entrada_minima(lancs))
    parseado = parse_ecd(arquivo.conteudo)
    assert [lanc.numero for lanc in parseado.lancamentos] == ["1", "2", "3"]
    assert parseado.lancamentos[1].valor_total == Decimal("250.50")


def test_roundtrip_saldos_periodicos() -> None:
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    assert len(parseado.saldos_periodicos) == 1
    periodo = parseado.saldos_periodicos[0]
    assert periodo.inicio == date(2025, 3, 1)
    assert periodo.fim == date(2025, 3, 31)
    assert len(periodo.saldos) == 1
    saldo = periodo.saldos[0]
    assert saldo.codigo_conta == "1.1.1.01"
    assert saldo.saldo_final == Decimal("1000.00")
    assert saldo.indicador_saldo_final == "D"


def test_hash_estavel_round_trip() -> None:
    """Hash do gerador == hash recalculado pelo parser do mesmo arquivo."""
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    assert parseado.hash_arquivo == arquivo.hash_sha256


def test_total_linhas_bate_com_9999() -> None:
    arquivo = gerar_ecd(_entrada_minima())
    parseado = parse_ecd(arquivo.conteudo)
    # Validação interna já roda em parse_ecd; aqui só consulta atributo.
    assert parseado.total_linhas == arquivo.total_linhas


# ── Erros ───────────────────────────────────────────────────────────────────


def test_arquivo_vazio_levanta() -> None:
    with pytest.raises(EcdInvalido, match="vazio"):
        parse_ecd(b"")


def test_arquivo_sem_0000_levanta() -> None:
    with pytest.raises(EcdInvalido, match="0000 ausente"):
        parse_ecd(b"|I001|0|\n|9999|2|\n")


def test_arquivo_sem_9999_levanta() -> None:
    """Arquivo sem totalizador final é rejeitado."""
    arquivo = gerar_ecd(_entrada_minima())
    # Remove a linha 9999 do final.
    linhas = arquivo.conteudo.decode("latin-1").splitlines(keepends=True)
    sem_9999 = "".join(ln for ln in linhas if not ln.startswith("|9999|"))
    with pytest.raises(EcdInvalido, match="9999"):
        parse_ecd(sem_9999.encode("latin-1"))


def test_9999_inconsistente_levanta() -> None:
    """Arquivo com 9999 declarando total errado."""
    arquivo = gerar_ecd(_entrada_minima())
    texto = arquivo.conteudo.decode("latin-1")
    # Adultera o 9999 para um número arbitrariamente errado.
    linhas = texto.splitlines(keepends=True)
    for i, ln in enumerate(linhas):
        if ln.startswith("|9999|"):
            linhas[i] = "|9999|99999|\n"
            break
    with pytest.raises(EcdInvalido, match="declarado=99999"):
        parse_ecd("".join(linhas).encode("latin-1"))


def test_partida_desbalanceada_levanta() -> None:
    """Forja um arquivo onde o I250 não bate com o I200 — parser detecta."""
    # Constrói uma ECD artificial linha-a-linha com débito ≠ crédito.
    linhas = [
        "|0000|10.00|0||01012025|31122025|TESTE|12345678000190|SP||3550308||0|0|0||0|N|0||S|N|N|N||S|\n",
        "|0001|0|\n",
        "|0990|3|\n",
        "|I001|0|\n",
        "|I050|01012025|01|A|4|D|1.1.1.01||CAIXA|\n",
        "|I050|01012025|01|A|3|C|4.1.01||RECEITA|\n",
        "|I200|99|15032025|1000,00|N|\n",
        "|I250|1.1.1.01||1000,00|D|HIST||\n",
        "|I250|4.1.01||500,00|C|HIST||\n",  # crédito errado
        "|I990|6|\n",
        "|9001|0|\n",
        "|9900|0000|1|\n",
        "|9900|0001|1|\n",
        "|9900|0990|1|\n",
        "|9900|I001|1|\n",
        "|9900|I050|2|\n",
        "|9900|I200|1|\n",
        "|9900|I250|2|\n",
        "|9900|I990|1|\n",
        "|9900|9001|1|\n",
        "|9900|9900|11|\n",
        "|9900|9990|1|\n",
        "|9900|9999|1|\n",
        "|9990|13|\n",
        "|9999|23|\n",
    ]
    with pytest.raises(EcdInvalido, match="débitos.*créditos"):
        parse_ecd("".join(linhas).encode("latin-1"))


def test_conta_orfa_em_i250_levanta() -> None:
    """Partida referencia conta que não está no I050."""
    linhas = [
        "|0000|10.00|0||01012025|31122025|TESTE|12345678000190|SP||3550308||0|0|0||0|N|0||S|N|N|N||S|\n",
        "|0001|0|\n",
        "|0990|3|\n",
        "|I001|0|\n",
        "|I050|01012025|01|A|4|D|1.1.1.01||CAIXA|\n",
        "|I200|1|15032025|100,00|N|\n",
        "|I250|1.1.1.01||100,00|D|HIST||\n",
        "|I250|9.9.9.99||100,00|C|HIST||\n",  # conta inexistente
        "|I990|5|\n",
        "|9001|0|\n",
        "|9999|11|\n",
    ]
    with pytest.raises(EcdInvalido, match="9.9.9.99"):
        parse_ecd("".join(linhas).encode("latin-1"))
