"""Golden tests do resolver puro de código IBGE 7-dígitos (Fase 2 PR6)."""

from __future__ import annotations

from app.modules.empresa.ibge import resolver_ibge


# Lista reduzida realista da BrasilAPI /ibge/municipios/v1/SP — usada em vários testes
_MUNICIPIOS_SP = [
    {"nome": "SAO PAULO", "codigo_ibge": "3550308"},
    {"nome": "CAMPINAS", "codigo_ibge": "3509502"},
    {"nome": "SAO BERNARDO DO CAMPO", "codigo_ibge": "3548708"},
    {"nome": "GUARULHOS", "codigo_ibge": "3518800"},
    # Caso real: BrasilAPI retorna em maiúsculas mas IBGE oficial é mixed case
    {"nome": "RIBEIRAO PRETO", "codigo_ibge": "3543402"},
]


class TestResolverIbge:
    def test_match_com_acento_no_input(self) -> None:
        # BrasilAPI retornou "São Paulo" (com acento) — lista tem "SAO PAULO"
        assert resolver_ibge("São Paulo", _MUNICIPIOS_SP) == "3550308"

    def test_match_caixa_alta(self) -> None:
        assert resolver_ibge("SÃO PAULO", _MUNICIPIOS_SP) == "3550308"

    def test_match_caixa_baixa(self) -> None:
        assert resolver_ibge("são paulo", _MUNICIPIOS_SP) == "3550308"

    def test_match_com_espacos_extras(self) -> None:
        assert resolver_ibge("  Campinas  ", _MUNICIPIOS_SP) == "3509502"

    def test_municipio_inexistente_retorna_none(self) -> None:
        assert resolver_ibge("Cidade Fantasia", _MUNICIPIOS_SP) is None

    def test_nome_vazio_retorna_none(self) -> None:
        assert resolver_ibge("", _MUNICIPIOS_SP) is None

    def test_nome_none_retorna_none(self) -> None:
        assert resolver_ibge(None, _MUNICIPIOS_SP) is None

    def test_lista_vazia_retorna_none(self) -> None:
        assert resolver_ibge("São Paulo", []) is None

    def test_homonimo_resolvido_pela_lista_da_uf(self) -> None:
        # "Boa Vista" existe em RR (1400100) e PB (2502151).
        # Caller passa só a lista da UF correta → sem ambiguidade.
        municipios_rr = [{"nome": "BOA VISTA", "codigo_ibge": "1400100"}]
        municipios_pb = [{"nome": "BOA VISTA", "codigo_ibge": "2502151"}]
        assert resolver_ibge("Boa Vista", municipios_rr) == "1400100"
        assert resolver_ibge("Boa Vista", municipios_pb) == "2502151"

    def test_codigo_nao_7_digitos_descartado(self) -> None:
        # Defesa contra payload corrompido — IBGE válido sempre tem 7 dígitos
        municipios_ruim = [{"nome": "BAD", "codigo_ibge": "12345"}]
        assert resolver_ibge("BAD", municipios_ruim) is None

    def test_codigo_com_letras_descartado(self) -> None:
        municipios_ruim = [{"nome": "BAD", "codigo_ibge": "ABC1234"}]
        assert resolver_ibge("BAD", municipios_ruim) is None

    def test_codigo_inteiro_convertido_para_string(self) -> None:
        # BrasilAPI por vezes serializa codigo_ibge como int — aceitar e converter
        municipios = [{"nome": "TESTE", "codigo_ibge": 3550308}]
        assert resolver_ibge("Teste", municipios) == "3550308"
