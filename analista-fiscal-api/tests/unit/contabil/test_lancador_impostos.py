"""Golden tests — lançador de impostos apurados (ApuracaoFiscal → LancamentoContabil).

Cobre:
  1. Função pura ``gerar_partidas_de_apuracao``: mapa D/C por tipo de tributo.
  2. ``_valor_apuracao``: extração do valor por tipo (usando output_jsonb canônico).
  3. Idempotência conceitual: função pura é determinística por definição.
  4. Regressão do bug ``resolver_contas``: conta de imposto ausente NÃO quebra
     os lotes core (nfe/transacao/etc.) — apenas ``lote_impostos`` falha.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.modules.contabil.lancador_auto import (
    ALGORITMO_VERSAO_IMPOSTOS,
    ApuracaoFatoView,
    ContasImpostos,
    gerar_partidas_de_apuracao,
)
from app.modules.contabil.lancador_service import _valor_apuracao


# ── Fixtures ─────────────────────────────────────────────────────────────────

_CONTAS_IMPOSTOS = ContasImpostos(
    das_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000001"),
    icms_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000002"),
    iss_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000003"),
    pis_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000004"),
    cofins_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000005"),
    irpj_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000006"),
    csll_recolher=uuid.UUID("a0000000-0000-0000-0000-000000000007"),
    impostos_sobre_receita=uuid.UUID("b0000000-0000-0000-0000-000000000001"),
    provisao_irpj_csll=uuid.UUID("b0000000-0000-0000-0000-000000000002"),
)

_COMP = date(2025, 3, 1)


def _view(tipo: str, valor: Decimal = Decimal("1000.00")) -> ApuracaoFatoView:
    return ApuracaoFatoView(
        id=uuid.uuid4(),
        competencia=_COMP,
        tipo=tipo,
        valor=valor,
    )


# ── Testes puros: gerar_partidas_de_apuracao ─────────────────────────────────


class TestGerarPartidasDeApuracao:
    def _debito(self, r, expected_conta: uuid.UUID) -> None:
        assert r is not None
        debitos = [p for p in r.partidas if p.tipo == "D"]
        assert len(debitos) == 1
        assert debitos[0].conta_id == expected_conta

    def _credito(self, r, expected_conta: uuid.UUID) -> None:
        assert r is not None
        creditos = [p for p in r.partidas if p.tipo == "C"]
        assert len(creditos) == 1
        assert creditos[0].conta_id == expected_conta

    def _balanceado(self, r) -> None:
        assert r is not None
        total_d = sum(p.valor for p in r.partidas if p.tipo == "D")
        total_c = sum(p.valor for p in r.partidas if p.tipo == "C")
        assert total_d == total_c

    # ── DAS — D impostos_sobre_receita / C das_recolher ──────────────────────

    def test_das_debito_impostos_sobre_receita(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.impostos_sobre_receita)

    def test_das_credito_das_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.das_recolher)

    def test_das_balanceado(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das"), _CONTAS_IMPOSTOS)
        self._balanceado(r)

    # ── ICMS — D impostos_sobre_receita / C icms_recolher ────────────────────

    def test_icms_debito_impostos_sobre_receita(self) -> None:
        r = gerar_partidas_de_apuracao(_view("icms"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.impostos_sobre_receita)

    def test_icms_credito_icms_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("icms"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.icms_recolher)

    # ── ISS — D impostos_sobre_receita / C iss_recolher ──────────────────────

    def test_iss_debito_impostos_sobre_receita(self) -> None:
        r = gerar_partidas_de_apuracao(_view("iss"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.impostos_sobre_receita)

    def test_iss_credito_iss_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("iss"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.iss_recolher)

    # ── PIS — D impostos_sobre_receita / C pis_recolher ──────────────────────

    def test_pis_debito_impostos_sobre_receita(self) -> None:
        r = gerar_partidas_de_apuracao(_view("pis"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.impostos_sobre_receita)

    def test_pis_credito_pis_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("pis"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.pis_recolher)

    # ── COFINS — D impostos_sobre_receita / C cofins_recolher ────────────────

    def test_cofins_debito_impostos_sobre_receita(self) -> None:
        r = gerar_partidas_de_apuracao(_view("cofins"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.impostos_sobre_receita)

    def test_cofins_credito_cofins_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("cofins"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.cofins_recolher)

    # ── IRPJ — D provisao_irpj_csll / C irpj_recolher ───────────────────────

    def test_irpj_debito_provisao_irpj_csll(self) -> None:
        r = gerar_partidas_de_apuracao(_view("irpj"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.provisao_irpj_csll)

    def test_irpj_credito_irpj_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("irpj"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.irpj_recolher)

    def test_irpj_balanceado(self) -> None:
        r = gerar_partidas_de_apuracao(_view("irpj"), _CONTAS_IMPOSTOS)
        self._balanceado(r)

    # ── CSLL — D provisao_irpj_csll / C csll_recolher ───────────────────────

    def test_csll_debito_provisao_irpj_csll(self) -> None:
        r = gerar_partidas_de_apuracao(_view("csll"), _CONTAS_IMPOSTOS)
        self._debito(r, _CONTAS_IMPOSTOS.provisao_irpj_csll)

    def test_csll_credito_csll_recolher(self) -> None:
        r = gerar_partidas_de_apuracao(_view("csll"), _CONTAS_IMPOSTOS)
        self._credito(r, _CONTAS_IMPOSTOS.csll_recolher)

    # ── Casos que retornam None ───────────────────────────────────────────────

    def test_dctf_retorna_none(self) -> None:
        r = gerar_partidas_de_apuracao(_view("dctf"), _CONTAS_IMPOSTOS)
        assert r is None

    def test_efd_contrib_retorna_none(self) -> None:
        r = gerar_partidas_de_apuracao(_view("efd_contrib"), _CONTAS_IMPOSTOS)
        assert r is None

    def test_valor_zero_retorna_none(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das", Decimal("0")), _CONTAS_IMPOSTOS)
        assert r is None

    def test_valor_negativo_retorna_none(self) -> None:
        r = gerar_partidas_de_apuracao(
            _view("icms", Decimal("-500.00")), _CONTAS_IMPOSTOS
        )
        assert r is None

    # ── Metadata ─────────────────────────────────────────────────────────────

    def test_origem_tipo_apuracao(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das"), _CONTAS_IMPOSTOS)
        assert r is not None
        assert r.origem_tipo == "apuracao"

    def test_versao_algoritmo_impostos(self) -> None:
        r = gerar_partidas_de_apuracao(_view("das"), _CONTAS_IMPOSTOS)
        assert r is not None
        assert r.versao == ALGORITMO_VERSAO_IMPOSTOS

    def test_competencia_primeiro_dia_do_mes(self) -> None:
        r = gerar_partidas_de_apuracao(_view("pis"), _CONTAS_IMPOSTOS)
        assert r is not None
        assert r.competencia.day == 1

    def test_historico_contem_tipo_e_competencia(self) -> None:
        r = gerar_partidas_de_apuracao(_view("irpj"), _CONTAS_IMPOSTOS)
        assert r is not None
        assert "IRPJ" in r.historico
        assert "2025-03" in r.historico

    def test_valor_quantizado_duas_casas(self) -> None:
        """Valor com mais de 2 casas é quantizado ROUND_HALF_EVEN."""
        r = gerar_partidas_de_apuracao(
            _view("das", Decimal("100.555")), _CONTAS_IMPOSTOS
        )
        assert r is not None
        for p in r.partidas:
            assert p.valor == Decimal("100.56")

    def test_total_property_balanceado(self) -> None:
        """LancamentoCandidato.total == soma dos débitos."""
        r = gerar_partidas_de_apuracao(_view("cofins", Decimal("300.00")), _CONTAS_IMPOSTOS)
        assert r is not None
        assert r.total == Decimal("300.00")


# ── _valor_apuracao: extração por output_jsonb ────────────────────────────────


class TestValorApuracao:
    def test_das_extrai_valor_das(self) -> None:
        # DAS usa chave "valor_das" no output_jsonb (fiscal/service.py:160).
        out: dict[str, object] = {"valor_das": "1500.00", "aliquota_efetiva": "0.05"}
        v = _valor_apuracao("das", out, None)
        assert v == Decimal("1500.00")

    def test_irpj_extrai_irpj_total(self) -> None:
        out = {"irpj_total": "2500.00", "irpj_devido": "2500.00"}
        v = _valor_apuracao("irpj", out, None)
        assert v == Decimal("2500.00")

    def test_csll_extrai_csll(self) -> None:
        out = {"csll": "900.00"}
        v = _valor_apuracao("csll", out, None)
        assert v == Decimal("900.00")

    def test_pis_extrai_tributo(self) -> None:
        out = {"tributo": "65.00"}
        v = _valor_apuracao("pis", out, None)
        assert v == Decimal("65.00")

    def test_cofins_extrai_tributo(self) -> None:
        out = {"tributo": "300.00"}
        v = _valor_apuracao("cofins", out, None)
        assert v == Decimal("300.00")

    def test_icms_extrai_icms_a_recolher(self) -> None:
        out = {"icms_a_recolher": "800.00"}
        v = _valor_apuracao("icms", out, None)
        assert v == Decimal("800.00")

    def test_iss_extrai_iss(self) -> None:
        out = {"iss": "200.00"}
        v = _valor_apuracao("iss", out, None)
        assert v == Decimal("200.00")

    def test_iss_legado_fallback_input(self) -> None:
        """ISS legado: output sem 'iss' → fallback para input_jsonb.valor."""
        out: dict[str, object] = {}
        inp = {"valor": "150.00"}
        v = _valor_apuracao("iss", out, inp)
        assert v == Decimal("150.00")

    def test_dctf_retorna_none(self) -> None:
        out: dict[str, object] = {}
        assert _valor_apuracao("dctf", out, None) is None

    def test_efd_contrib_retorna_none(self) -> None:
        out: dict[str, object] = {}
        assert _valor_apuracao("efd_contrib", out, None) is None

    def test_valor_zero_retorna_none(self) -> None:
        out: dict[str, object] = {"valor_das": "0.00"}
        assert _valor_apuracao("das", out, None) is None

    def test_valor_quantizado_duas_casas(self) -> None:
        out = {"tributo": "123.456"}
        v = _valor_apuracao("pis", out, None)
        assert v is not None
        assert v == Decimal("123.46")  # ROUND_HALF_EVEN


# ── Regressão do bug resolver_contas ─────────────────────────────────────────


class TestRegressionResolverContasCore:
    """
    Prova que ``resolver_contas`` (core) NÃO quebra quando contas de imposto
    estão ausentes do plano — simulando empresa que clonou antes de
    das_recolher/icms_recolher/etc. serem adicionadas ao dict.

    Antes da correção, ``resolver_contas`` iterava CODIGOS_PADRAO_LANCAMENTO_AUTO.items()
    inteiro — qualquer conta nova no dict que a empresa não tivesse causaria
    PlanoContasIncompleto em TODOS os lotes (nfe, transacao, etc.).
    Agora itera apenas ``_CHAVES_CORE`` — empresa antiga não é penalizada.
    """

    @pytest.mark.asyncio
    async def test_resolver_contas_nao_quebra_sem_contas_impostos(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from app.modules.contabil.lancador_service import LancadorService
        from app.modules.contabil.plano_referencial import (
            CODIGOS_PADRAO_LANCAMENTO_AUTO,
            _CHAVES_CORE,
            _CHAVES_IMPOSTOS,
        )

        # Simula empresa antiga: contas core OK, contas de imposto ausentes.
        codigos_core = {CODIGOS_PADRAO_LANCAMENTO_AUTO[k] for k in _CHAVES_CORE}
        codigos_impostos = {CODIGOS_PADRAO_LANCAMENTO_AUTO[k] for k in _CHAVES_IMPOSTOS}

        session = AsyncMock()

        async def por_codigo(empresa_id: object, codigo: str, *, em: object = None) -> object:
            if codigo in codigos_impostos:
                return None  # conta de imposto ausente
            if codigo in codigos_core:
                return SimpleNamespace(id=uuid.uuid4(), aceita_lancamento=True)
            return None

        repo = AsyncMock()
        repo.por_codigo = AsyncMock(side_effect=por_codigo)

        with patch(
            "app.modules.contabil.lancador_service.ContaContabilRepo",
            return_value=repo,
        ):
            # NÃO deve levantar PlanoContasIncompleto — contas core todas OK
            contas = await LancadorService().resolver_contas(
                session, uuid.uuid4(), date(2025, 1, 1)
            )
        assert contas.banco is not None
        assert contas.clientes is not None
        # Apenas _CHAVES_CORE foi consultada — contas de imposto NÃO foram buscadas.
        assert repo.por_codigo.await_count == len(_CHAVES_CORE)

    @pytest.mark.asyncio
    async def test_resolver_contas_impostos_levanta_quando_ausentes(self) -> None:
        """resolver_contas_impostos SIM falha quando conta de imposto está ausente."""
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from app.modules.contabil.lancador_service import LancadorService
        from app.shared.exceptions import PlanoContasIncompleto

        session = AsyncMock()

        async def por_codigo_nenhuma(empresa_id: object, codigo: str, *, em: object = None) -> None:
            return None  # todas as contas ausentes

        repo = AsyncMock()
        repo.por_codigo = AsyncMock(side_effect=por_codigo_nenhuma)

        with patch(
            "app.modules.contabil.lancador_service.ContaContabilRepo",
            return_value=repo,
        ):
            with pytest.raises(PlanoContasIncompleto):
                await LancadorService().resolver_contas_impostos(
                    session, uuid.uuid4(), date(2025, 1, 1)
                )
