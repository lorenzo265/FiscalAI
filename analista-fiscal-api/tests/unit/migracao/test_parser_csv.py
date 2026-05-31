"""Testes do parser CSV — balancete + razão (Sprint 18 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.migracao.parser_csv import (
    ALGORITMO_VERSAO,
    CsvInvalido,
    parse_balancete_csv,
    parse_razao_csv,
)


# ── Balancete ───────────────────────────────────────────────────────────────


def test_balancete_happy_path() -> None:
    """Balancete BR com separador ';' e decimais com vírgula."""
    csv = (
        "codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final\n"
        "1.1.1.01;Caixa;0,00;1500,00;500,00;1000,00\n"
        "4.1.01;Receita;0,00;0,00;1500,00;1500,00\n"
    )
    out = parse_balancete_csv(csv.encode("utf-8"))
    assert out.algoritmo_versao == ALGORITMO_VERSAO
    assert len(out.linhas) == 2
    caixa = out.linhas[0]
    assert caixa.codigo_conta == "1.1.1.01"
    assert caixa.descricao == "Caixa"
    assert caixa.saldo_final == Decimal("1000.00")
    assert caixa.debito == Decimal("1500.00")
    assert out.total_debitos == Decimal("1500.00")
    assert out.total_creditos == Decimal("2000.00")


def test_balancete_aceita_decimal_us() -> None:
    """Excel exportado com decimais ponto também funciona."""
    csv = (
        "codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final\n"
        "1.1.1.01;Caixa;0.00;1500.00;500.00;1000.00\n"
    )
    out = parse_balancete_csv(csv.encode("utf-8"))
    assert out.linhas[0].saldo_final == Decimal("1000.00")


def test_balancete_aceita_latin1_com_bom() -> None:
    """Excel BR exporta latin-1 com acentos — deve aceitar."""
    csv = (
        "codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final\n"
        "1.1.1.01;Caixa Geral;0,00;100,00;0,00;100,00\n"
    )
    out = parse_balancete_csv(csv.encode("latin-1"))
    assert out.linhas[0].descricao == "Caixa Geral"


def test_balancete_sem_cabecalho_obrigatorio_levanta() -> None:
    csv = (
        "codigo_conta;descricao;saldo_final\n"  # sem debito/credito/saldo_inicial
        "1.1.1.01;Caixa;1000,00\n"
    )
    with pytest.raises(CsvInvalido, match="obrigatórias"):
        parse_balancete_csv(csv.encode("utf-8"))


def test_balancete_vazio_levanta() -> None:
    with pytest.raises(CsvInvalido, match="vazio"):
        parse_balancete_csv(b"")


def test_balancete_so_cabecalho_levanta() -> None:
    csv = "codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final\n"
    with pytest.raises(CsvInvalido, match="sem linhas"):
        parse_balancete_csv(csv.encode("utf-8"))


def test_balancete_hash_estavel_idempotente() -> None:
    csv = (
        "codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final\n"
        "1.1.1.01;Caixa;0,00;100,00;0,00;100,00\n"
    ).encode("utf-8")
    a = parse_balancete_csv(csv)
    b = parse_balancete_csv(csv)
    assert a.hash_arquivo == b.hash_arquivo


# ── Razão ───────────────────────────────────────────────────────────────────


def test_razao_happy_path() -> None:
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        "15/03/2025;1.1.1.01;4.1.01;Recebimento serviço;1000,00\n"
        "20/03/2025;5.1.01;1.1.1.01;Pagamento fornecedor;500,00\n"
    )
    out = parse_razao_csv(csv.encode("utf-8"))
    assert out.algoritmo_versao == ALGORITMO_VERSAO
    assert len(out.lancamentos) == 2
    assert out.total_valor == Decimal("1500.00")
    primeiro = out.lancamentos[0]
    assert primeiro.data == date(2025, 3, 15)
    assert primeiro.conta_debito == "1.1.1.01"
    assert primeiro.conta_credito == "4.1.01"
    assert primeiro.valor == Decimal("1000.00")
    assert primeiro.chave_nfe_referenciada is None


def test_razao_data_iso_tambem_funciona() -> None:
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        "2025-03-15;1.1.1.01;4.1.01;Serviço;100,00\n"
    )
    out = parse_razao_csv(csv.encode("utf-8"))
    assert out.lancamentos[0].data == date(2025, 3, 15)


def test_razao_detecta_chave_nfe_no_historico() -> None:
    """Histórico com chave de 44 dígitos vira ``chave_nfe_referenciada``."""
    chave = "35250612345678000190550010000010011000000010"
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        f"15/03/2025;1.1.1.01;4.1.01;Receita NF-e {chave};1000,00\n"
    )
    out = parse_razao_csv(csv.encode("utf-8"))
    assert out.lancamentos[0].chave_nfe_referenciada == chave


def test_razao_valor_negativo_vira_estorno_com_inversao() -> None:
    """Sprint 19.7 PR4 (#39) — valor negativo inverte D/C automaticamente."""
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        "15/03/2025;1.1.1.01;4.1.01;Estorno receita;-100,00\n"
    )
    parseado = parse_razao_csv(csv.encode("utf-8"))
    assert len(parseado.lancamentos) == 1
    lanc = parseado.lancamentos[0]
    assert lanc.estorno is True
    assert lanc.valor == Decimal("100.00")
    # Conta original D=1.1.1.01 → vira C; original C=4.1.01 → vira D.
    assert lanc.conta_debito == "4.1.01"
    assert lanc.conta_credito == "1.1.1.01"


def test_razao_valor_zero_levanta() -> None:
    """Valor 0 continua rejeitado (fato vazio)."""
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        "15/03/2025;1.1.1.01;4.1.01;Teste;0,00\n"
    )
    with pytest.raises(CsvInvalido, match="zero"):
        parse_razao_csv(csv.encode("utf-8"))


def test_razao_data_invalida_levanta() -> None:
    csv = (
        "data;conta_debito;conta_credito;historico;valor\n"
        "15-03-2025;1.1.1.01;4.1.01;Teste;100,00\n"
    )
    with pytest.raises(CsvInvalido, match="Linha 2"):
        parse_razao_csv(csv.encode("utf-8"))


def test_razao_sem_cabecalho_obrigatorio_levanta() -> None:
    csv = (
        "data;conta_debito;historico;valor\n"  # falta conta_credito
        "15/03/2025;1.1.1.01;Teste;100,00\n"
    )
    with pytest.raises(CsvInvalido, match="obrigatórias"):
        parse_razao_csv(csv.encode("utf-8"))
