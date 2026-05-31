"""Golden tests do classificador NCM (Sprint 19.7 PR4 #5)."""

from __future__ import annotations

from app.modules.contabil.classificacao_ncm import (
    ALGORITMO_VERSAO,
    SugestaoClassificacao,
    sugerir_conta_por_ncm,
)


class TestHeuristicaNcm:
    def test_capitulo_22_bebidas_vira_estoques(self) -> None:
        sug = sugerir_conta_por_ncm("22030000")
        assert sug is not None
        assert sug.chave_conta_sugerida == "estoques"
        assert sug.capitulo_ncm == "22"
        assert "Bebidas" in sug.descricao_capitulo
        assert sug.confianca == "alta"

    def test_capitulo_87_veiculos_vira_imobilizado(self) -> None:
        sug = sugerir_conta_por_ncm("87032310")
        assert sug is not None
        assert sug.chave_conta_sugerida == "imobilizado"
        assert sug.confianca == "alta"

    def test_capitulo_85_eletronicos_confianca_media(self) -> None:
        sug = sugerir_conta_por_ncm("8525.81.10")
        assert sug is not None
        assert sug.chave_conta_sugerida == "estoques"
        assert sug.confianca == "media"

    def test_ncm_pontuado_e_aceito(self) -> None:
        sug = sugerir_conta_por_ncm("22.03.00.00")
        assert sug is not None
        assert sug.capitulo_ncm == "22"

    def test_capitulo_fora_do_mapa_devolve_none(self) -> None:
        # Capítulo 49 (livros) — não está coberto na heurística.
        assert sugerir_conta_por_ncm("49011000") is None

    def test_ncm_vazio_ou_none_devolve_none(self) -> None:
        assert sugerir_conta_por_ncm(None) is None
        assert sugerir_conta_por_ncm("") is None
        assert sugerir_conta_por_ncm("   ") is None

    def test_ncm_alfanumerico_devolve_none(self) -> None:
        assert sugerir_conta_por_ncm("ABCD1234") is None


class TestInteracaoComCfop:
    def test_cfop_ja_classificado_suprime_sugestao(self) -> None:
        """CFOP 1102 (compra revenda) já vai pra 'estoques' — sem sugestão."""
        assert sugerir_conta_por_ncm("22030000", cfop="1102") is None

    def test_cfop_fallback_libera_sugestao_ncm(self) -> None:
        """CFOP 1949 (outras entradas) cai em fallback — NCM ajuda a sugerir."""
        sug = sugerir_conta_por_ncm("22030000", cfop="1949")
        assert sug is not None
        assert sug.chave_conta_sugerida == "estoques"

    def test_cfop_None_segue_heuristica_pura(self) -> None:
        sug = sugerir_conta_por_ncm("87032310", cfop=None)
        assert sug is not None
        assert sug.chave_conta_sugerida == "imobilizado"


def test_algoritmo_versao_v1() -> None:
    assert ALGORITMO_VERSAO == "classificacao_ncm.v1"


def test_dataclass_carrega_citacao_para_lgpd_audit() -> None:
    """§8.5 — toda sugestão precisa carregar citação textual."""
    sug = sugerir_conta_por_ncm("22030000")
    assert isinstance(sug, SugestaoClassificacao)
    assert sug.descricao_capitulo  # não-vazio
    assert sug.capitulo_ncm.isdigit()
