"""Golden tests do classificador determinístico de CFOP de entrada."""

from __future__ import annotations

import pytest

from app.modules.contabil.classificador_cfop import (
    ALGORITMO_VERSAO,
    CONTA_FALLBACK_ENTRADA,
    classificar_conta_debito_entrada,
)


class TestClassificarCfopEntrada:
    @pytest.mark.parametrize(
        ("cfop", "esperado"),
        [
            # Industrialização
            ("1101", "estoques"),
            ("2101", "estoques"),
            # Comercialização (revenda)
            ("1102", "estoques"),
            ("2102", "estoques"),
            # Ativo imobilizado
            ("1556", "imobilizado"),
            ("2556", "imobilizado"),
            # Serviço em prestação
            ("1128", "despesa_servicos"),
            ("2128", "despesa_servicos"),
            # Comunicação
            ("1933", "despesa_servicos"),
            ("2933", "despesa_servicos"),
        ],
    )
    def test_cfops_mapeados(self, cfop: str, esperado: str) -> None:
        assert classificar_conta_debito_entrada(cfop) == esperado

    def test_aceita_cfop_pontuado(self) -> None:
        """Formato `1.102` deve ser equivalente a `1102` (RICMS comum)."""
        assert classificar_conta_debito_entrada("1.102") == "estoques"
        assert classificar_conta_debito_entrada("2.556") == "imobilizado"

    def test_cfop_none_retorna_fallback(self) -> None:
        assert classificar_conta_debito_entrada(None) == CONTA_FALLBACK_ENTRADA

    def test_cfop_vazio_retorna_fallback(self) -> None:
        assert classificar_conta_debito_entrada("") == CONTA_FALLBACK_ENTRADA
        assert classificar_conta_debito_entrada("   ") == CONTA_FALLBACK_ENTRADA

    def test_cfop_formato_invalido_retorna_fallback(self) -> None:
        # Apenas 3 dígitos
        assert classificar_conta_debito_entrada("102") == CONTA_FALLBACK_ENTRADA
        # Letras
        assert classificar_conta_debito_entrada("ABCD") == CONTA_FALLBACK_ENTRADA
        # Mais de 4 dígitos
        assert classificar_conta_debito_entrada("11023") == CONTA_FALLBACK_ENTRADA

    def test_cfop_desconhecido_retorna_fallback(self) -> None:
        """CFOP válido mas fora do mapa MVP — degrada para outras_despesas."""
        assert classificar_conta_debito_entrada("9999") == CONTA_FALLBACK_ENTRADA
        assert classificar_conta_debito_entrada("1949") == CONTA_FALLBACK_ENTRADA

    def test_cfop_saida_5xxx_nao_mapeado(self) -> None:
        """CFOPs de saída (5.xxx/6.xxx) não estão neste classificador."""
        assert classificar_conta_debito_entrada("5102") == CONTA_FALLBACK_ENTRADA
        assert classificar_conta_debito_entrada("6102") == CONTA_FALLBACK_ENTRADA

    def test_algoritmo_versao_e_versionado(self) -> None:
        assert ALGORITMO_VERSAO.startswith("cfop-classifier-")
