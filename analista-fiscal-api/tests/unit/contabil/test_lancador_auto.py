"""Golden tests do motor automático de lançamentos (Sprint 9 PR2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from app.modules.contabil.lancador_auto import (
    ALGORITMO_VERSAO,
    ContasAuto,
    DepreciacaoFatoView,
    NfFatoView,
    ProvisaoFatoView,
    TransacaoFatoView,
    gerar_partidas_de_depreciacao,
    gerar_partidas_de_nfe,
    gerar_partidas_de_provisao,
    gerar_partidas_de_transacao,
)


def _contas() -> ContasAuto:
    """Lookup com UUIDs sintéticos — basta serem distinguíveis."""
    return ContasAuto(
        clientes=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        fornecedores=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        banco=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        receita_servicos=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        receita_vendas=uuid.UUID("55555555-5555-5555-5555-555555555555"),
        outras_receitas=uuid.UUID("66666666-6666-6666-6666-666666666666"),
        outras_despesas=uuid.UUID("77777777-7777-7777-7777-777777777777"),
        despesa_depreciacao=uuid.UUID("88888888-8888-8888-8888-888888888888"),
        depreciacao_acumulada=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        despesa_pessoal=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        encargos_sociais=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        provisao_ferias=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        provisao_13=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        inss_recolher=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        fgts_recolher=uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
    )


# ── NF saída/entrada ────────────────────────────────────────────────────────


class TestNfeLancamento:
    def test_nfse_saida_d_clientes_c_receita_servicos(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfse",
            direcao="saida",
            valor_total=Decimal("1000.00"),
            emitida_em=datetime(2026, 5, 15, 10, 0),
            numero="00012345",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        assert r.origem_tipo == "nfe"
        assert r.origem_id == nf.id
        assert r.competencia == date(2026, 5, 1)
        assert r.versao == ALGORITMO_VERSAO

        debitos = [p for p in r.partidas if p.tipo == "D"]
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert len(debitos) == 1 and len(creditos) == 1
        assert debitos[0].conta_id == contas.clientes
        assert debitos[0].valor == Decimal("1000.00")
        assert creditos[0].conta_id == contas.receita_servicos
        assert creditos[0].valor == Decimal("1000.00")

    def test_nfe_saida_credita_receita_vendas(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="saida",
            valor_total=Decimal("500"),
            emitida_em=datetime(2026, 4, 10),
            numero="42",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert creditos[0].conta_id == contas.receita_vendas

    def test_nf_entrada_d_despesa_c_fornecedor(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="entrada",
            valor_total=Decimal("300"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-1",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert debitos[0].conta_id == contas.outras_despesas
        assert creditos[0].conta_id == contas.fornecedores
        assert "entrada" in r.historico.lower()


# ── Transação bancária ──────────────────────────────────────────────────────


class TestTransacaoLancamento:
    def test_credit_d_banco_c_outras_receitas(self) -> None:
        contas = _contas()
        tx = TransacaoFatoView(
            id=uuid.uuid4(),
            valor=Decimal("250"),
            tipo="CREDIT",
            data_transacao=date(2026, 5, 10),
            descricao="PIX recebido",
        )
        r = gerar_partidas_de_transacao(tx, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert debitos[0].conta_id == contas.banco
        assert creditos[0].conta_id == contas.outras_receitas
        assert debitos[0].valor == Decimal("250")

    def test_debit_d_outras_despesas_c_banco_modulo(self) -> None:
        """DEBIT é armazenado negativo; valor da partida usa módulo."""
        contas = _contas()
        tx = TransacaoFatoView(
            id=uuid.uuid4(),
            valor=Decimal("-180"),
            tipo="DEBIT",
            data_transacao=date(2026, 5, 12),
            descricao="Pagamento",
        )
        r = gerar_partidas_de_transacao(tx, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert debitos[0].conta_id == contas.outras_despesas
        assert debitos[0].valor == Decimal("180")  # positivo
        assert creditos[0].conta_id == contas.banco


# ── Depreciação ─────────────────────────────────────────────────────────────


class TestDepreciacaoLancamento:
    def test_depreciacao_positiva_d_despesa_c_acumulada(self) -> None:
        contas = _contas()
        d = DepreciacaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            valor_depreciado=Decimal("833.33"),
        )
        r = gerar_partidas_de_depreciacao(d, contas)
        assert r is not None
        debitos = [p for p in r.partidas if p.tipo == "D"]
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert debitos[0].conta_id == contas.despesa_depreciacao
        assert creditos[0].conta_id == contas.depreciacao_acumulada
        assert debitos[0].valor == Decimal("833.33")

    def test_depreciacao_zero_retorna_none(self) -> None:
        contas = _contas()
        d = DepreciacaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            valor_depreciado=Decimal("0"),
        )
        assert gerar_partidas_de_depreciacao(d, contas) is None


# ── Provisão ────────────────────────────────────────────────────────────────


class TestProvisaoLancamento:
    def test_ferias_d_despesa_pessoal_c_provisao_ferias(self) -> None:
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="ferias",
            valor_provisao=Decimal("1111.11"),
        )
        r = gerar_partidas_de_provisao(p, contas)
        assert r is not None
        d = [x for x in r.partidas if x.tipo == "D"][0]
        c = [x for x in r.partidas if x.tipo == "C"][0]
        assert d.conta_id == contas.despesa_pessoal
        assert c.conta_id == contas.provisao_ferias
        assert d.valor == Decimal("1111.11")
        assert "férias" in r.historico.lower()

    def test_13_salario_d_despesa_c_provisao_13(self) -> None:
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="13_salario",
            valor_provisao=Decimal("833.33"),
        )
        r = gerar_partidas_de_provisao(p, contas)
        assert r is not None
        c = [x for x in r.partidas if x.tipo == "C"][0]
        assert c.conta_id == contas.provisao_13

    def test_inss_ferias_d_encargos_c_inss_recolher(self) -> None:
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="inss_ferias",
            valor_provisao=Decimal("222.22"),
        )
        r = gerar_partidas_de_provisao(p, contas)
        assert r is not None
        d = [x for x in r.partidas if x.tipo == "D"][0]
        c = [x for x in r.partidas if x.tipo == "C"][0]
        assert d.conta_id == contas.encargos_sociais
        assert c.conta_id == contas.inss_recolher

    def test_fgts_13_d_encargos_c_fgts_recolher(self) -> None:
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="fgts_13",
            valor_provisao=Decimal("66.67"),
        )
        r = gerar_partidas_de_provisao(p, contas)
        assert r is not None
        c = [x for x in r.partidas if x.tipo == "C"][0]
        assert c.conta_id == contas.fgts_recolher

    def test_provisao_zero_retorna_none(self) -> None:
        """Linha de INSS para SN/MEI (valor=0) NÃO gera lançamento."""
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="inss_ferias",
            valor_provisao=Decimal("0"),
        )
        assert gerar_partidas_de_provisao(p, contas) is None

    def test_tipo_desconhecido_retorna_none(self) -> None:
        contas = _contas()
        p = ProvisaoFatoView(
            id=uuid.uuid4(),
            competencia=date(2026, 5, 1),
            tipo="invalido_xyz",
            valor_provisao=Decimal("100"),
        )
        assert gerar_partidas_de_provisao(p, contas) is None


# ── Invariante de partidas dobradas ─────────────────────────────────────────


class TestPartidasDobradas:
    def test_todo_lancamento_tem_total_d_igual_total_c(self) -> None:
        """Para cada conversor, garante D=C automaticamente."""
        contas = _contas()
        casos: list[object] = [
            gerar_partidas_de_nfe(
                NfFatoView(
                    id=uuid.uuid4(),
                    tipo="nfse",
                    direcao="saida",
                    valor_total=Decimal("123.45"),
                    emitida_em=datetime(2026, 1, 1),
                    numero="1",
                ),
                contas,
            ),
            gerar_partidas_de_nfe(
                NfFatoView(
                    id=uuid.uuid4(),
                    tipo="nfe",
                    direcao="entrada",
                    valor_total=Decimal("500"),
                    emitida_em=datetime(2026, 1, 1),
                    numero="2",
                ),
                contas,
            ),
            gerar_partidas_de_transacao(
                TransacaoFatoView(
                    id=uuid.uuid4(),
                    valor=Decimal("100"),
                    tipo="CREDIT",
                    data_transacao=date(2026, 1, 1),
                    descricao=None,
                ),
                contas,
            ),
            gerar_partidas_de_depreciacao(
                DepreciacaoFatoView(
                    id=uuid.uuid4(),
                    competencia=date(2026, 5, 1),
                    valor_depreciado=Decimal("100"),
                ),
                contas,
            ),
            gerar_partidas_de_provisao(
                ProvisaoFatoView(
                    id=uuid.uuid4(),
                    competencia=date(2026, 5, 1),
                    tipo="ferias",
                    valor_provisao=Decimal("50"),
                ),
                contas,
            ),
        ]
        for r in casos:
            assert r is not None
            total_d = sum((p.valor for p in r.partidas if p.tipo == "D"), Decimal("0"))
            total_c = sum((p.valor for p in r.partidas if p.tipo == "C"), Decimal("0"))
            assert total_d == total_c
            assert total_d > Decimal("0")
