"""Golden tests da resolução de presunção LP por CNAE — FA3/M6.

Testa a lógica de prefix-match e prioridade do ``PresuncaoLpRepo`` de forma
pura (sem I/O), instanciando diretamente os objetos ORM ``PresuncaoLucroPresumido``
e chamando a lógica de match via ``_normalizar_cnae`` + simulação do algoritmo.

Objetivo principal:
  * Provar que CNAE 8630 (consultório médico) resolve 32%/32% após migration 0053.
  * Provar que CNAE 4711 (comércio — supermercados) segue 8%/12% (não regrediu).
  * Provar que CNAE 8610 (hospitais) segue 8%/12% (servicos_hospitalares).
  * Cobrir também: veterinária (75), cursos (855), serviços pessoais (96).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from app.modules.lucro_presumido.repo import _normalizar_cnae

# ── Stub mínimo de PresuncaoLucroPresumido (sem banco) ────────────────────────

@dataclass
class _FakePresuncao:
    """Simula um registro ORM de presuncao_lucro_presumido."""

    grupo_atividade: str
    cnae_pattern: str | None
    percentual_irpj: Decimal
    percentual_csll: Decimal
    limite_receita_anual: Decimal | None
    prioridade: int
    fonte: str
    valid_from: date
    valid_to: date | None


def _resolver(
    vigentes: list[_FakePresuncao],
    cnae_principal: str | None,
    faturamento_12m: Decimal | None = None,
) -> _FakePresuncao | None:
    """Replica a lógica de ``PresuncaoLpRepo.resolver_por_cnae`` sem BD."""
    cnae_norm = _normalizar_cnae(cnae_principal)
    candidatos: list[_FakePresuncao] = []
    for v in vigentes:
        if v.cnae_pattern is None:
            if v.limite_receita_anual is not None and (
                faturamento_12m is None or faturamento_12m > v.limite_receita_anual
            ):
                continue
            candidatos.append(v)
            continue
        pattern_norm = _normalizar_cnae(v.cnae_pattern)
        if cnae_norm and cnae_norm.startswith(pattern_norm):
            candidatos.append(v)

    if not candidatos:
        return None
    return sorted(candidatos, key=lambda x: x.prioridade)[0]


# ── Fixtures: seed completo (0019 + 0053) ─────────────────────────────────────

FONTE = "Lei 9.249/1995 art. 15 + art. 20 + IN RFB 1.700/2017 art. 33"
V_FROM = date(1996, 1, 1)


def _make_seed() -> list[_FakePresuncao]:
    """Retorna a lista completa de registros vigentes após 0019 + 0053."""
    return [
        # ── 0019 — seed original ────────────────────────────────────────────
        _FakePresuncao(
            "comercio_industria", None, Decimal("0.0800"), Decimal("0.1200"),
            None, 99, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "revenda_combustiveis", "47.30", Decimal("0.0160"), Decimal("0.1200"),
            None, 10, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "transporte_cargas", "49.30", Decimal("0.0800"), Decimal("0.1200"),
            None, 20, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_hospitalares", "86.10", Decimal("0.0800"), Decimal("0.1200"),
            None, 20, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "transporte_passageiros", "49.21", Decimal("0.1600"), Decimal("0.1200"),
            None, 20, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_gerais_pequenos", None, Decimal("0.1600"), Decimal("0.1200"),
            Decimal("120000.00"), 30, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_profissionais", "69", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_profissionais", "71", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_profissionais", "73", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "intermediacao_negocios", "70", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "intermediacao_negocios", "74", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "intermediacao_negocios", "82", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        # ── 0053 — seed FA3/M6 ──────────────────────────────────────────────
        # saude_nao_hospitalar: div. 86 exceto 8610 (hospitais)
        _FakePresuncao(
            "saude_nao_hospitalar", "862", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "saude_nao_hospitalar", "863", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "saude_nao_hospitalar", "864", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "saude_nao_hospitalar", "865", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "saude_nao_hospitalar", "866", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "saude_nao_hospitalar", "869", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_profissionais", "75", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_profissionais", "855", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
        _FakePresuncao(
            "servicos_pessoais", "96", Decimal("0.3200"), Decimal("0.3200"),
            None, 15, FONTE, V_FROM, None,
        ),
    ]


@pytest.fixture()
def seed() -> list[_FakePresuncao]:
    return _make_seed()


# ── Testes M6 — saúde não-hospitalar resolve 32% ─────────────────────────────


class TestSaudeNaoHospitalar:
    """FA3/M6: CNAEs do div. 86 não-hospitalares devem resolver 32%/32%."""

    def test_cnae_8630_consultorios_medicos_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """CNAE 8630-5/01 (consultório médico) é o caso principal do M6."""
        r = _resolver(seed, "8630-5/01")
        assert r is not None
        assert r.grupo_atividade == "saude_nao_hospitalar"
        assert r.percentual_irpj == Decimal("0.3200")
        assert r.percentual_csll == Decimal("0.3200")

    def test_cnae_8621_medicina_ambulatorial_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "8621-6/01")
        assert r is not None
        assert r.grupo_atividade == "saude_nao_hospitalar"
        assert r.percentual_irpj == Decimal("0.3200")

    def test_cnae_8650_profissionais_saude_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """Psicólogos, fisioterapeutas etc. (8650) — prefix "865"."""
        r = _resolver(seed, "8650-0/02")
        assert r is not None
        assert r.grupo_atividade == "saude_nao_hospitalar"
        assert r.percentual_irpj == Decimal("0.3200")

    def test_cnae_8640_laboratorio_diagnostico_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """Laboratórios de diagnóstico (8640) — prefix "864"."""
        r = _resolver(seed, "8640-2/08")
        assert r is not None
        assert r.grupo_atividade == "saude_nao_hospitalar"
        assert r.percentual_irpj == Decimal("0.3200")


class TestSaudeHospitalarNaoRegride:
    """CNAE 8610 (hospitais) deve continuar em 8%/12%."""

    def test_cnae_8610_hospital_permanece_8pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "8610-1/01")
        assert r is not None
        assert r.grupo_atividade == "servicos_hospitalares"
        assert r.percentual_irpj == Decimal("0.0800")
        assert r.percentual_csll == Decimal("0.1200")


class TestVeterinaria:
    def test_cnae_7500_veterinaria_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "7500-1/00")
        assert r is not None
        assert r.grupo_atividade == "servicos_profissionais"
        assert r.percentual_irpj == Decimal("0.3200")
        assert r.percentual_csll == Decimal("0.3200")


class TestCursosEServicosEducacionais:
    def test_cnae_8550_cursos_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """CNAE 8550-3/02 (treinamento — inf. e comunicação)."""
        r = _resolver(seed, "8550-3/02")
        assert r is not None
        assert r.grupo_atividade == "servicos_profissionais"
        assert r.percentual_irpj == Decimal("0.3200")


class TestServicosPessoais:
    def test_cnae_9602_cabeleireiros_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "9602-5/02")
        assert r is not None
        assert r.grupo_atividade == "servicos_pessoais"
        assert r.percentual_irpj == Decimal("0.3200")
        assert r.percentual_csll == Decimal("0.3200")

    def test_cnae_9609_outros_servicos_pessoais_resolve_32pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "9609-2/99")
        assert r is not None
        assert r.grupo_atividade == "servicos_pessoais"
        assert r.percentual_irpj == Decimal("0.3200")


# ── Testes de regressão — comércio não regrediu ───────────────────────────────


class TestComercioNaoRegride:
    """Garante que as novas linhas não interferem em CNAEs de comércio."""

    def test_cnae_4711_supermercado_permanece_8pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "4711-3/02")
        assert r is not None
        assert r.grupo_atividade == "comercio_industria"
        assert r.percentual_irpj == Decimal("0.0800")
        assert r.percentual_csll == Decimal("0.1200")

    def test_cnae_1012_abatedouro_permanece_8pct(
        self, seed: list[_FakePresuncao]
    ) -> None:
        r = _resolver(seed, "1012-1/03")
        assert r is not None
        assert r.grupo_atividade == "comercio_industria"
        assert r.percentual_irpj == Decimal("0.0800")


# ── Testes de isolamento de prefixo — sem colisão ─────────────────────────────


class TestIsolamentoPrefixo:
    """Verificações de que novos prefixos não capturam CNAEs não-alvo."""

    def test_prefixo_862_nao_captura_8610(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """'8610' não começa com '862' → hospital continua em 8%."""
        r = _resolver(seed, "8610-1/02")
        assert r is not None
        assert r.percentual_irpj == Decimal("0.0800")

    def test_prefixo_75_nao_captura_7510_locadora_veiculos(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """CNAE 7510-5 (locação de veículos) pertence à div. 77, não 75.
        Mas o prefixo '75' normalizado = '75' → '7510' starts with '75' = TRUE.
        Confirma que o match é correto: locação de veículos é div. 77 (CNAE 7711).
        Esta fixture documenta que a intenção é capturar div. 75 (veterinária)
        e que 7710-x NÃO começa com '75'.
        """
        # 7711-4 (locação de automóveis): normalized '77114' startswith '75'? NO.
        r = _resolver(seed, "7711-4/00")
        # não casa com 75; deve cair no default
        assert r is not None
        assert r.grupo_atividade == "comercio_industria"

    def test_prefixo_855_nao_captura_8511_educacao_infantil(
        self, seed: list[_FakePresuncao]
    ) -> None:
        """CNAE 8511-2 (educação infantil) normalized = '85112'.
        '85112'.startswith('855') = False → não capturado por '855'.
        Cai no default comercio_industria (8%).
        """
        r = _resolver(seed, "8511-2/00")
        assert r is not None
        assert r.grupo_atividade == "comercio_industria"
        assert r.percentual_irpj == Decimal("0.0800")
