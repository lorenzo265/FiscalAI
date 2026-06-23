"""Testes unitários — lógica de onboarding por CNPJ."""

from __future__ import annotations

from decimal import Decimal

from app.modules.empresa.onboarding import (
    derivar_regime_por_porte,
    mapear_dados_brasil_api,
    sugerir_anexo_simples,
)
from app.modules.empresa.schemas import AnexoSimples, RegimeTributario


class TestDerivarRegimePorPorte:
    def test_mei_por_porte(self) -> None:
        assert derivar_regime_por_porte("MEI", None) == RegimeTributario.MEI

    def test_mei_porte_maiusculo(self) -> None:
        assert derivar_regime_por_porte("mei", None) == RegimeTributario.MEI

    def test_simples_nacional_me_sem_faturamento(self) -> None:
        assert derivar_regime_por_porte("ME", None) == RegimeTributario.SIMPLES_NACIONAL

    def test_simples_nacional_epp_faturamento_dentro(self) -> None:
        fat = Decimal("2_000_000")
        assert derivar_regime_por_porte("EPP", fat) == RegimeTributario.SIMPLES_NACIONAL

    def test_simples_nacional_epp_limite_exato(self) -> None:
        fat = Decimal("4_800_000")
        assert derivar_regime_por_porte("EPP", fat) == RegimeTributario.SIMPLES_NACIONAL

    def test_lucro_presumido_faturamento_acima_limite_sn(self) -> None:
        fat = Decimal("4_800_001")
        assert derivar_regime_por_porte("EPP", fat) == RegimeTributario.LUCRO_PRESUMIDO

    def test_lucro_presumido_porte_demais(self) -> None:
        assert derivar_regime_por_porte("DEMAIS", Decimal("1_000_000")) == RegimeTributario.LUCRO_PRESUMIDO

    def test_cnae_vedado_ao_sn_resulta_em_lp(self) -> None:
        # 6422100 = banco múltiplo — vedado ao SN
        resultado = derivar_regime_por_porte("ME", Decimal("500_000"), cnae_principal="6422100")
        assert resultado == RegimeTributario.LUCRO_PRESUMIDO

    def test_cnae_permitido_nao_afeta_sn(self) -> None:
        resultado = derivar_regime_por_porte("ME", Decimal("500_000"), cnae_principal="6201501")
        assert resultado == RegimeTributario.SIMPLES_NACIONAL

    def test_porte_vazio_faturamento_baixo(self) -> None:
        resultado = derivar_regime_por_porte("", Decimal("100_000"))
        assert resultado == RegimeTributario.SIMPLES_NACIONAL

    # ── MEI Caminhoneiro / Transportador Autônomo (LC 188/2021) ──────────────
    def test_mei_transportador_faturamento_acima_81k_dentro_limite(self) -> None:
        # CNAE 4930202 (transporte carga interestadual) + faturamento R$200k
        # → ainda cabe no MEI Caminhoneiro (teto R$251.600).
        resultado = derivar_regime_por_porte(
            "MEI", Decimal("200_000"), cnae_principal="4930202"
        )
        assert resultado == RegimeTributario.MEI

    def test_mei_transportador_faturamento_no_limite(self) -> None:
        resultado = derivar_regime_por_porte(
            "MEI", Decimal("251_600"), cnae_principal="4930201"
        )
        assert resultado == RegimeTributario.MEI

    def test_mei_transportador_faturamento_acima_limite_cai_para_sn(self) -> None:
        resultado = derivar_regime_por_porte(
            "MEI", Decimal("251_600.01"), cnae_principal="4930202"
        )
        assert resultado == RegimeTributario.SIMPLES_NACIONAL

    def test_mei_nao_transportador_faturamento_acima_81k_cai_para_sn(self) -> None:
        # CNAE de TI (não-transportador) com R$150k → estourou MEI comum, vai p/ SN.
        resultado = derivar_regime_por_porte(
            "MEI", Decimal("150_000"), cnae_principal="6201501"
        )
        assert resultado == RegimeTributario.SIMPLES_NACIONAL

    # ── CNAEs vedados ampliados (LC 123/2006 art. 17 X, XII, XIV) ────────────
    def test_locacao_mao_de_obra_vedada(self) -> None:
        # 7820500 — locação de MO temporária (art. 17 XII)
        resultado = derivar_regime_por_porte(
            "ME", Decimal("500_000"), cnae_principal="7820500"
        )
        assert resultado == RegimeTributario.LUCRO_PRESUMIDO

    def test_incorporacao_imobiliaria_vedada(self) -> None:
        # 4110700 — incorporação de empreendimentos imobiliários (art. 17 XIV)
        resultado = derivar_regime_por_porte(
            "EPP", Decimal("3_000_000"), cnae_principal="4110700"
        )
        assert resultado == RegimeTributario.LUCRO_PRESUMIDO

    def test_atacado_cigarros_vedado(self) -> None:
        # 4636202 — atacado de cigarros (art. 17 X)
        resultado = derivar_regime_por_porte(
            "ME", Decimal("500_000"), cnae_principal="4636202"
        )
        assert resultado == RegimeTributario.LUCRO_PRESUMIDO

    def test_advocacia_permitida_no_sn(self) -> None:
        # 6911701 (advocacia) — LC 147/2014 permite SN sob Anexo IV.
        # Audit propôs adicionar à vedação, mas isso seria incorreto.
        resultado = derivar_regime_por_porte(
            "ME", Decimal("500_000"), cnae_principal="6911701"
        )
        assert resultado == RegimeTributario.SIMPLES_NACIONAL

    def test_contabilidade_permitida_no_sn(self) -> None:
        # 6920602 (contabilidade) — permitida no SN.
        resultado = derivar_regime_por_porte(
            "ME", Decimal("500_000"), cnae_principal="6920602"
        )
        assert resultado == RegimeTributario.SIMPLES_NACIONAL


class TestSugerirAnexoSimples:
    def test_cnae_ti_retorna_anexo_iii(self) -> None:
        assert sugerir_anexo_simples("6201501") == AnexoSimples.III

    def test_cnae_contabilidade_retorna_anexo_iii(self) -> None:
        assert sugerir_anexo_simples("6920602") == AnexoSimples.III

    def test_cnae_comercio_varejista_retorna_anexo_i(self) -> None:
        # Divisão 47 = comércio varejista
        assert sugerir_anexo_simples("4711301") == AnexoSimples.I

    def test_cnae_industria_retorna_anexo_ii(self) -> None:
        # Divisão 10 = fabricação de alimentos
        assert sugerir_anexo_simples("1011201") == AnexoSimples.II

    def test_cnae_none_retorna_none(self) -> None:
        assert sugerir_anexo_simples(None) is None

    def test_cnae_vazio_retorna_none(self) -> None:
        assert sugerir_anexo_simples("") is None


class TestMapearDadosBrasilApi:
    def test_mapeia_campos_basicos(self) -> None:
        dados_raw: dict[str, object] = {
            "razao_social": "EMPRESA TESTE LTDA",
            "nome_fantasia": "Teste",
            "porte": "ME",
            "cnae_fiscal": 6201501,
            "cnae_fiscal_descricao": "Desenvolvimento de programas de computador",
            "municipio": "São Paulo",
            "uf": "SP",
            "descricao_situacao_cadastral": "ATIVA",
        }
        resultado = mapear_dados_brasil_api(dados_raw)
        assert resultado["razao_social"] == "EMPRESA TESTE LTDA"
        assert resultado["porte"] == "ME"
        assert resultado["cnae_principal"] == "6201501"
        assert resultado["municipio"] == "São Paulo"
        assert resultado["uf"] == "SP"
        assert resultado["situacao"] == "ATIVA"

    def test_mapeia_sem_nome_fantasia(self) -> None:
        dados_raw: dict[str, object] = {
            "razao_social": "EMPRESA LTDA",
            "nome_fantasia": "",
            "porte": "EPP",
            "cnae_fiscal": 4711301,
            "descricao_situacao_cadastral": "ATIVA",
        }
        resultado = mapear_dados_brasil_api(dados_raw)
        assert resultado["nome_fantasia"] is None

    def test_cnae_com_pontuacao_normalizado(self) -> None:
        dados_raw: dict[str, object] = {
            "razao_social": "X",
            "porte": "ME",
            "cnae_fiscal": "62.01-5/01",
            "descricao_situacao_cadastral": "ATIVA",
        }
        resultado = mapear_dados_brasil_api(dados_raw)
        assert "." not in str(resultado["cnae_principal"])
        assert "-" not in str(resultado["cnae_principal"])
