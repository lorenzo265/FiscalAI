"""Golden tests do motor automático de lançamentos (Sprint 9 PR2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from app.modules.contabil.lancador_auto import (
    ALGORITMO_VERSAO,
    ContasAuto,
    DepreciacaoFatoView,
    FolhaFatoView,
    NfFatoView,
    ProvisaoFatoView,
    TransacaoFatoView,
    gerar_partidas_de_depreciacao,
    gerar_partidas_de_folha,
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
        irrf_funcionarios_recolher=uuid.UUID(
            "01010101-0101-0101-0101-010101010101"
        ),
        salarios_pagar=uuid.UUID("02020202-0202-0202-0202-020202020202"),
        estoques=uuid.UUID("10101010-1010-1010-1010-101010101010"),
        imobilizado=uuid.UUID("20202020-2020-2020-2020-202020202020"),
        despesa_servicos=uuid.UUID("30303030-3030-3030-3030-303030303030"),
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

    def test_nf_entrada_sem_cfop_fallback_outras_despesas(self) -> None:
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

    def test_nf_entrada_cfop_1102_revenda_debita_estoques(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="entrada",
            valor_total=Decimal("1500"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-2",
            cfop="1102",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        assert debitos[0].conta_id == contas.estoques
        assert "estoques" in r.historico.lower()

    def test_nf_entrada_cfop_2556_imobilizado(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="entrada",
            valor_total=Decimal("12000"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-3",
            cfop="2.556",  # formato pontuado também aceito
        )
        r = gerar_partidas_de_nfe(nf, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        assert debitos[0].conta_id == contas.imobilizado

    def test_nf_entrada_cfop_1933_comunicacao_servicos(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="entrada",
            valor_total=Decimal("180"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-4",
            cfop="1933",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        assert debitos[0].conta_id == contas.despesa_servicos

    def test_nf_entrada_cfop_desconhecido_fallback(self) -> None:
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="entrada",
            valor_total=Decimal("99"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-5",
            cfop="9999",  # não mapeado
        )
        r = gerar_partidas_de_nfe(nf, contas)
        debitos = [p for p in r.partidas if p.tipo == "D"]
        assert debitos[0].conta_id == contas.outras_despesas

    def test_nf_saida_ignora_cfop(self) -> None:
        """CFOP de saída (5.xxx/6.xxx) não muda a conta de receita."""
        contas = _contas()
        nf = NfFatoView(
            id=uuid.uuid4(),
            tipo="nfe",
            direcao="saida",
            valor_total=Decimal("750"),
            emitida_em=datetime(2026, 3, 5),
            numero="X-6",
            cfop="5102",
        )
        r = gerar_partidas_de_nfe(nf, contas)
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert creditos[0].conta_id == contas.receita_vendas


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


# ── Sprint 19.7 PR1 (#10) — folha mensal ───────────────────────────────────


def _folha(
    *,
    total_proventos: str = "10000.00",
    total_inss_empregado: str = "1000.00",
    total_irrf: str = "500.00",
    total_fgts_empregador: str = "800.00",
    competencia: date = date(2026, 5, 1),
) -> FolhaFatoView:
    return FolhaFatoView(
        id=uuid.UUID("0a0a0a0a-0a0a-0a0a-0a0a-0a0a0a0a0a0a"),
        competencia=competencia,
        total_proventos=Decimal(total_proventos),
        total_inss_empregado=Decimal(total_inss_empregado),
        total_irrf=Decimal(total_irrf),
        total_fgts_empregador=Decimal(total_fgts_empregador),
    )


class TestFolhaLancamento:
    def test_folha_canonica_emite_6_partidas_balanceadas(self) -> None:
        """5 contas envolvidas, 6 partidas (D pessoal + 3 créditos retenções +
        D encargos + C FGTS). Total débitos == total créditos."""
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        assert cand.origem_tipo == "folha"
        assert cand.historico == "Folha mensal 2026-05"
        assert len(cand.partidas) == 6
        total_d = sum(
            (p.valor for p in cand.partidas if p.tipo == "D"), Decimal("0")
        )
        total_c = sum(
            (p.valor for p in cand.partidas if p.tipo == "C"), Decimal("0")
        )
        # D Pessoal R$ 10.000 + D Encargos R$ 800 = R$ 10.800
        # C Salários R$ 8.500 + C INSS R$ 1.000 + C IRRF R$ 500 + C FGTS R$ 800 = R$ 10.800
        assert total_d == Decimal("10800.00")
        assert total_c == Decimal("10800.00")

    def test_liquido_pagar_eh_proventos_menos_retencoes(self) -> None:
        """Líquido a pagar = total_proventos - inss - irrf (NÃO subtrai FGTS
        — FGTS é encargo empregador, não desconto empregado)."""
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        salarios = next(
            p for p in cand.partidas
            if p.tipo == "C" and p.conta_id == contas.salarios_pagar
        )
        assert salarios.valor == Decimal("8500.00")  # 10000 - 1000 - 500

    def test_inss_credita_conta_correta(self) -> None:
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        inss = next(
            p for p in cand.partidas
            if p.tipo == "C" and p.conta_id == contas.inss_recolher
        )
        assert inss.valor == Decimal("1000.00")

    def test_irrf_credita_conta_correta(self) -> None:
        """IRRF retido na folha vai pra conta nova `irrf_funcionarios_recolher`
        (2.1.3.03), não pra 'inss_recolher'."""
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        irrf = next(
            p for p in cand.partidas
            if p.tipo == "C" and p.conta_id == contas.irrf_funcionarios_recolher
        )
        assert irrf.valor == Decimal("500.00")

    def test_fgts_eh_par_despesa_passivo_separado(self) -> None:
        """FGTS empregador = par D Encargos / C FGTS — não desconta do líquido."""
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        encargos_d = next(
            p for p in cand.partidas
            if p.tipo == "D" and p.conta_id == contas.encargos_sociais
        )
        fgts_c = next(
            p for p in cand.partidas
            if p.tipo == "C" and p.conta_id == contas.fgts_recolher
        )
        assert encargos_d.valor == Decimal("800.00")
        assert fgts_c.valor == Decimal("800.00")

    def test_folha_zero_proventos_pula(self) -> None:
        """Folha sem funcionários ativos (total=0) → None, sem lançamento."""
        contas = _contas()
        cand = gerar_partidas_de_folha(
            _folha(total_proventos="0"), contas
        )
        assert cand is None

    def test_folha_sem_irrf_nao_emite_partida_zerada(self) -> None:
        """IRRF=0 (funcionário isento / redutor Lei 15.270/2025) — a linha de
        IRRF NÃO vira partida (R$0,00 não se lança, e o validador de partida
        dobrada rejeita valor não positivo). As partidas restantes seguem
        balanceadas (D==C) e TODAS com valor > 0."""
        contas = _contas()
        cand = gerar_partidas_de_folha(
            _folha(total_irrf="0", total_inss_empregado="500"), contas
        )
        assert cand is not None
        # A conta de IRRF a recolher nem aparece quando o IRRF é zero.
        assert all(
            p.conta_id != contas.irrf_funcionarios_recolher
            for p in cand.partidas
        )
        # Nenhuma partida com valor <= 0 (não passaria no validador).
        assert all(p.valor > Decimal("0") for p in cand.partidas)
        total_d = sum(
            (p.valor for p in cand.partidas if p.tipo == "D"), Decimal("0")
        )
        total_c = sum(
            (p.valor for p in cand.partidas if p.tipo == "C"), Decimal("0")
        )
        assert total_d == total_c

    def test_folha_competencia_normalizada_pro_primeiro_dia(self) -> None:
        """competência pode vir como dia 15 — normaliza pro dia 1."""
        contas = _contas()
        cand = gerar_partidas_de_folha(
            _folha(competencia=date(2026, 5, 15)), contas
        )
        assert cand is not None
        assert cand.competencia == date(2026, 5, 1)
        assert cand.data_lancamento == date(2026, 5, 1)

    def test_origem_id_e_folha_id(self) -> None:
        """origem_id == folha.id pra idempotência via UNIQUE (origem_tipo, origem_id)."""
        contas = _contas()
        cand = gerar_partidas_de_folha(_folha(), contas)
        assert cand is not None
        assert cand.origem_tipo == "folha"
        assert cand.origem_id == uuid.UUID("0a0a0a0a-0a0a-0a0a-0a0a-0a0a0a0a0a0a")
