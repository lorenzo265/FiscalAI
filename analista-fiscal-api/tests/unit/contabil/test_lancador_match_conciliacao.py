"""Testes do consumo de match conciliação em ``gerar_partidas_de_transacao``
(Sprint 19.7 PR4 #6)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.modules.contabil.lancador_auto import (
    ContasAuto,
    MatchDocumentoFatoView,
    TransacaoFatoView,
    gerar_partidas_de_transacao,
)


def _contas() -> ContasAuto:
    return ContasAuto(
        clientes=uuid4(),
        fornecedores=uuid4(),
        banco=uuid4(),
        receita_servicos=uuid4(),
        receita_vendas=uuid4(),
        outras_receitas=uuid4(),
        outras_despesas=uuid4(),
        despesa_depreciacao=uuid4(),
        depreciacao_acumulada=uuid4(),
        despesa_pessoal=uuid4(),
        encargos_sociais=uuid4(),
        provisao_ferias=uuid4(),
        provisao_13=uuid4(),
        inss_recolher=uuid4(),
        fgts_recolher=uuid4(),
        irrf_funcionarios_recolher=uuid4(),
        salarios_pagar=uuid4(),
        estoques=uuid4(),
        imobilizado=uuid4(),
        despesa_servicos=uuid4(),
    )


def test_credit_com_match_nf_saida_credita_clientes() -> None:
    """Recebimento via PIX casado com NF-e saída → C Clientes (baixa duplicata)."""
    contas = _contas()
    match = MatchDocumentoFatoView(
        documento_id=uuid4(),
        documento_tipo="nfe",
        documento_direcao="saida",
        documento_numero="1001",
    )
    tx = TransacaoFatoView(
        id=uuid4(),
        valor=Decimal("5000.00"),
        tipo="CREDIT",
        data_transacao=date(2026, 4, 5),
        descricao="PIX cliente acme",
        match=match,
    )
    lanc = gerar_partidas_de_transacao(tx, contas)
    assert lanc.origem_tipo == "transacao"
    assert "1001" in lanc.historico
    assert "Recebimento NF" in lanc.historico
    # 2 partidas: D Banco / C Clientes
    debitos = [p for p in lanc.partidas if p.tipo == "D"]
    creditos = [p for p in lanc.partidas if p.tipo == "C"]
    assert len(debitos) == 1 and debitos[0].conta_id == contas.banco
    assert len(creditos) == 1 and creditos[0].conta_id == contas.clientes


def test_debit_com_match_nf_entrada_debita_fornecedores() -> None:
    """Boleto pago casado com NF-e entrada → D Fornecedores (baixa duplicata)."""
    contas = _contas()
    match = MatchDocumentoFatoView(
        documento_id=uuid4(),
        documento_tipo="nfe",
        documento_direcao="entrada",
        documento_numero="555",
    )
    tx = TransacaoFatoView(
        id=uuid4(),
        valor=Decimal("-2000.00"),
        tipo="DEBIT",
        data_transacao=date(2026, 4, 6),
        descricao="boleto fornecedor xyz",
        match=match,
    )
    lanc = gerar_partidas_de_transacao(tx, contas)
    assert "Pagamento NF" in lanc.historico
    assert "555" in lanc.historico
    debitos = [p for p in lanc.partidas if p.tipo == "D"]
    creditos = [p for p in lanc.partidas if p.tipo == "C"]
    assert len(debitos) == 1 and debitos[0].conta_id == contas.fornecedores
    assert len(creditos) == 1 and creditos[0].conta_id == contas.banco


def test_credit_sem_match_cai_em_outras_receitas() -> None:
    """Backward-compat — sem match, comportamento v06 preservado."""
    contas = _contas()
    tx = TransacaoFatoView(
        id=uuid4(),
        valor=Decimal("100.00"),
        tipo="CREDIT",
        data_transacao=date(2026, 4, 7),
        descricao="depósito desconhecido",
    )
    lanc = gerar_partidas_de_transacao(tx, contas)
    creditos = [p for p in lanc.partidas if p.tipo == "C"]
    assert creditos[0].conta_id == contas.outras_receitas


def test_credit_com_match_nf_entrada_mismatch_direcional_cai_fallback() -> None:
    """CREDIT × NF entrada não faz sentido (cliente paga fornecedor?) — fallback."""
    contas = _contas()
    match = MatchDocumentoFatoView(
        documento_id=uuid4(),
        documento_tipo="nfe",
        documento_direcao="entrada",  # mismatch direcional
        documento_numero="999",
    )
    tx = TransacaoFatoView(
        id=uuid4(),
        valor=Decimal("100.00"),
        tipo="CREDIT",
        data_transacao=date(2026, 4, 8),
        descricao="estranho",
        match=match,
    )
    lanc = gerar_partidas_de_transacao(tx, contas)
    creditos = [p for p in lanc.partidas if p.tipo == "C"]
    # Cai em outras_receitas (não em clientes), match suspeito ignorado.
    assert creditos[0].conta_id == contas.outras_receitas


def test_debit_com_match_nfse_saida_mismatch_cai_fallback() -> None:
    """DEBIT × NF saída também não bate — fallback outras_despesas."""
    contas = _contas()
    match = MatchDocumentoFatoView(
        documento_id=uuid4(),
        documento_tipo="nfse",
        documento_direcao="saida",
        documento_numero="42",
    )
    tx = TransacaoFatoView(
        id=uuid4(),
        valor=Decimal("-200.00"),
        tipo="DEBIT",
        data_transacao=date(2026, 4, 9),
        descricao="estranho",
        match=match,
    )
    lanc = gerar_partidas_de_transacao(tx, contas)
    debitos = [p for p in lanc.partidas if p.tipo == "D"]
    assert debitos[0].conta_id == contas.outras_despesas
