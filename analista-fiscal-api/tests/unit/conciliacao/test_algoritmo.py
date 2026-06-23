"""Golden tests do algoritmo de conciliação (Sprint 7 PR3).

Cobre todas as regras documentadas em ``algoritmo.py``: sinal compatível,
pontuação por valor e data, CNPJ na descrição, e composições.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.modules.conciliacao.algoritmo import (
    ALGORITMO_VERSAO,
    LIMIAR_AUTO,
    LIMIAR_SUGERIDA,
    DocumentoView,
    TransacaoView,
    pontuar_match,
)

# ── factories ────────────────────────────────────────────────────────────────


def _credito(
    valor: str = "1000.00",
    data: date = date(2026, 4, 15),
    descricao: str | None = "PIX recebido",
) -> TransacaoView:
    return TransacaoView(
        id=uuid.uuid4(),
        valor=Decimal(valor),
        tipo="CREDIT",
        data_transacao=data,
        descricao=descricao,
    )


def _debito(
    valor: str = "-1000.00",
    data: date = date(2026, 4, 15),
    descricao: str | None = "Pagamento fornecedor",
) -> TransacaoView:
    return TransacaoView(
        id=uuid.uuid4(),
        valor=Decimal(valor),
        tipo="DEBIT",
        data_transacao=data,
        descricao=descricao,
    )


def _nf_saida(
    valor: str = "1000.00",
    data: date = date(2026, 4, 15),
    cnpj_dest: str | None = "98765432000110",
) -> DocumentoView:
    return DocumentoView(
        id=uuid.uuid4(),
        direcao="saida",
        valor_total=Decimal(valor),
        emitida_em_data=data,
        cnpj_emitente="12345678000195",
        cnpj_destinatario=cnpj_dest,
    )


def _nf_entrada(
    valor: str = "1000.00",
    data: date = date(2026, 4, 15),
    cnpj_emit: str = "98765432000110",
) -> DocumentoView:
    return DocumentoView(
        id=uuid.uuid4(),
        direcao="entrada",
        valor_total=Decimal(valor),
        emitida_em_data=data,
        cnpj_emitente=cnpj_emit,
        cnpj_destinatario="12345678000195",
    )


# ── sinal compatível ────────────────────────────────────────────────────────


class TestSinalCompativel:
    def test_credit_com_nf_entrada_score_zero(self) -> None:
        r = pontuar_match(_credito(), _nf_entrada())
        assert r.pontos == 0
        assert r.sinal_compativel is False
        assert "sinal_incompativel" in r.breakdown

    def test_debit_com_nf_saida_score_zero(self) -> None:
        r = pontuar_match(_debito(), _nf_saida())
        assert r.pontos == 0
        assert r.sinal_compativel is False

    def test_credit_com_nf_saida_pontua(self) -> None:
        r = pontuar_match(_credito(), _nf_saida())
        assert r.pontos > 0
        assert r.sinal_compativel is True

    def test_debit_com_nf_entrada_pontua(self) -> None:
        r = pontuar_match(_debito(), _nf_entrada())
        assert r.pontos > 0


# ── valor ────────────────────────────────────────────────────────────────────


class TestValor:
    def test_valor_exato_pontua_60(self) -> None:
        r = pontuar_match(
            _credito(valor="1000.00", descricao="nada"),
            _nf_saida(valor="1000.00", cnpj_dest=None),
        )
        # +60 (valor) +25 (data exata) — sem CNPJ na descrição
        assert r.pontos == 85
        assert any("valor_exato" in c for c in r.breakdown)

    def test_valor_proximo_5_reais_pontua_30(self) -> None:
        r = pontuar_match(
            _credito(valor="1004.50", descricao="nada"),
            _nf_saida(valor="1000.00", cnpj_dest=None),
        )
        # +30 (proximo) +25 (data exata) = 55
        assert r.pontos == 55
        assert any("valor_proximo" in c for c in r.breakdown)

    def test_valor_divergente_50_reais_score_zero(self) -> None:
        r = pontuar_match(
            _credito(valor="1100.00"),
            _nf_saida(valor="1000.00"),
        )
        assert r.pontos == 0
        assert any("valor_divergente" in c for c in r.breakdown)

    def test_valor_entre_5_e_50_nao_pontua_mas_continua(self) -> None:
        """Diferença R$ 20 — não ganha pontos de valor, mas data ainda pontua."""
        r = pontuar_match(
            _credito(valor="1020.00", descricao="nada"),
            _nf_saida(valor="1000.00", cnpj_dest=None),
        )
        # 0 (valor) + 25 (data exata) = 25
        assert r.pontos == 25

    def test_debit_signed_negativo_compara_em_modulo(self) -> None:
        """DEBIT armazenado como -1000; deve casar com NF de R$ 1000 (entrada)."""
        r = pontuar_match(
            _debito(valor="-1000.00"),
            _nf_entrada(valor="1000.00"),
        )
        assert any("valor_exato" in c for c in r.breakdown)


# ── data ─────────────────────────────────────────────────────────────────────


class TestData:
    def test_data_exata_pontua_25(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", data=date(2026, 4, 15), descricao="x"),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest=None),
        )
        # 60 + 25
        assert r.delta_dias == 0
        assert r.pontos == 85

    def test_data_1_dia_pontua_20(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", data=date(2026, 4, 16), descricao="x"),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest=None),
        )
        # 60 + 20
        assert r.delta_dias == 1
        assert r.pontos == 80

    def test_data_3_dias_pontua_10(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", data=date(2026, 4, 18), descricao="x"),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest=None),
        )
        # 60 + 10
        assert r.delta_dias == 3
        assert r.pontos == 70

    def test_data_10_dias_nao_pontua(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", data=date(2026, 4, 25), descricao="x"),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest=None),
        )
        # 60 (valor) + 0 (data > 5 dias)
        assert r.pontos == 60


# ── CNPJ na descrição ────────────────────────────────────────────────────────


class TestCnpjDescricao:
    def test_cnpj_na_descricao_adiciona_15(self) -> None:
        r = pontuar_match(
            _credito(
                valor="1000",
                data=date(2026, 4, 25),
                descricao="TED de 98765432000110 LTDA",
            ),
            _nf_saida(
                valor="1000", data=date(2026, 4, 15), cnpj_dest="98765432000110"
            ),
        )
        # 60 (valor) + 0 (data fora) + 15 (CNPJ) = 75
        assert r.pontos == 75
        assert any("cnpj_contraparte" in c for c in r.breakdown)

    def test_cnpj_formatado_na_descricao_tambem_pontua(self) -> None:
        r = pontuar_match(
            _credito(
                valor="1000",
                data=date(2026, 4, 25),
                descricao="Recebimento 98.765.432/0001-10",
            ),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest="98765432000110"),
        )
        assert any("cnpj_contraparte" in c for c in r.breakdown)

    def test_cnpj_ausente_na_descricao_nao_pontua(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", descricao="apenas isso"),
            _nf_saida(valor="1000", cnpj_dest="98765432000110"),
        )
        assert all("cnpj_contraparte" not in c for c in r.breakdown)

    def test_descricao_none_nao_quebra(self) -> None:
        r = pontuar_match(
            _credito(descricao=None), _nf_saida(cnpj_dest="98765432000110")
        )
        assert r.sinal_compativel is True


# ── score final / classificação ──────────────────────────────────────────────


class TestClassificacao:
    def test_auto_match_valor_exato_data_exata_cnpj(self) -> None:
        r = pontuar_match(
            _credito(
                valor="1000",
                data=date(2026, 4, 15),
                descricao="TED 98765432000110",
            ),
            _nf_saida(
                valor="1000", data=date(2026, 4, 15), cnpj_dest="98765432000110"
            ),
        )
        # 60 + 25 + 15 = 100
        assert r.pontos == 100
        assert r.auto_match is True
        assert r.sugere_match is True

    def test_apenas_sugerida(self) -> None:
        r = pontuar_match(
            _credito(valor="1000", data=date(2026, 4, 19), descricao="x"),
            _nf_saida(valor="1000", data=date(2026, 4, 15), cnpj_dest=None),
        )
        # 60 (valor) + 10 (4 dias) = 70 → SUGERIDA
        assert LIMIAR_SUGERIDA <= r.pontos < LIMIAR_AUTO
        assert r.sugere_match is True
        assert r.auto_match is False

    def test_versao_no_resultado(self) -> None:
        r = pontuar_match(_credito(), _nf_saida())
        assert r.versao == ALGORITMO_VERSAO

    def test_score_clampado_em_100(self) -> None:
        """Mesmo se todos os critérios pontuassem o máximo possível."""
        r = pontuar_match(
            _credito(
                valor="1000",
                data=date(2026, 4, 15),
                descricao="98765432000110",
            ),
            _nf_saida(
                valor="1000", data=date(2026, 4, 15), cnpj_dest="98765432000110"
            ),
        )
        assert 0 <= r.pontos <= 100
