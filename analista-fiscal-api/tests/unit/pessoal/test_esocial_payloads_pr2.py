"""Golden tests dos novos eventos eSocial Sprint 19.7 PR2 (#13).

Cobre S-2205, S-2206, S-2230, S-2298, S-3000.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.pessoal.esocial_payloads import (
    ALGORITMO_VERSAO,
    AfastamentoInput,
    AlteracaoCadastralInput,
    AlteracaoContratoInput,
    EmpregadorInput,
    ExclusaoInput,
    ReintegracaoInput,
    TrabalhadorInput,
    gerar_s2205_alteracao_cadastral,
    gerar_s2206_alteracao_contrato,
    gerar_s2230_afastamento,
    gerar_s2298_reintegracao,
    gerar_s3000_exclusao,
)
from app.shared.types import JsonObject

EMP = EmpregadorInput(cnpj="12345678000190", razao_social="Acme LTDA")
TRAB = TrabalhadorInput(cpf="11122233344", nome="Maria Souza")


def _common(p: JsonObject, tipo: str) -> None:
    assert p["tipo"] == tipo
    assert p["versao_leiaute"] == "S-1.3"
    assert p["algoritmo_versao"] == ALGORITMO_VERSAO
    assert p["ide_empregador"] == {"tpInsc": 1, "nrInsc": "12345678000190"}


# ── S-2205 — Alteração Cadastral ───────────────────────────────────────────


class TestS2205:
    def test_alteracao_nome_e_estado_civil(self) -> None:
        inp = AlteracaoCadastralInput(
            data_alteracao=date(2026, 3, 15),
            novo_nome="Maria Souza Lima",
            novo_estado_civil="casado",
        )
        p = gerar_s2205_alteracao_cadastral(EMP, TRAB, inp)
        _common(p, "S-2205")
        assert p["ide_trabalhador"] == {"cpfTrab": "11122233344"}
        alt = p["alteracao"]
        assert isinstance(alt, dict)
        assert alt["dtAlteracao"] == "2026-03-15"
        dados = alt["dadosTrabalhador"]
        assert isinstance(dados, dict)
        assert dados["nmTrab"] == "Maria Souza Lima"
        assert dados["estCiv"] == 2  # casado
        # dtNascto não foi fornecido — não aparece.
        assert "dtNascto" not in dados

    def test_apenas_data_nascimento(self) -> None:
        inp = AlteracaoCadastralInput(
            data_alteracao=date(2026, 4, 1),
            nova_data_nascimento=date(1991, 6, 15),
        )
        p = gerar_s2205_alteracao_cadastral(EMP, TRAB, inp)
        alt = p["alteracao"]
        assert isinstance(alt, dict)
        dados = alt["dadosTrabalhador"]
        assert isinstance(dados, dict)
        assert dados == {"dtNascto": "1991-06-15"}

    def test_estado_civil_invalido_e_ignorado(self) -> None:
        inp = AlteracaoCadastralInput(
            data_alteracao=date(2026, 4, 1),
            novo_estado_civil="enrolado",
        )
        p = gerar_s2205_alteracao_cadastral(EMP, TRAB, inp)
        alt = p["alteracao"]
        assert isinstance(alt, dict)
        dados = alt["dadosTrabalhador"]
        assert isinstance(dados, dict)
        # Estado civil desconhecido não popula estCiv (fail-soft).
        assert "estCiv" not in dados


# ── S-2206 — Alteração Contratual ──────────────────────────────────────────


class TestS2206:
    def test_promocao_com_salario_e_jornada(self) -> None:
        inp = AlteracaoContratoInput(
            data_alteracao=date(2026, 5, 1),
            novo_cargo="Analista Sênior",
            novo_salario=Decimal("8500"),
            nova_jornada_semanal_horas=Decimal("44"),
            motivo_alteracao="promocao",
        )
        p = gerar_s2206_alteracao_contrato(EMP, TRAB, inp)
        _common(p, "S-2206")
        assert p["ide_vinculo"] == {"cpfTrab": "11122233344"}
        alt = p["alt_contratual"]
        assert isinstance(alt, dict)
        assert alt["dtAlteracao"] == "2026-05-01"
        assert alt["tpAltContratual"] == "1"  # promoção
        contrato = alt["infoContrato"]
        assert isinstance(contrato, dict)
        assert contrato == {
            "nmCargo": "Analista Sênior",
            "vrSalFx": "8500",
            "undSalFixo": 5,
            "qtdHrsSem": "44",
        }

    def test_reajuste_apenas_salario(self) -> None:
        inp = AlteracaoContratoInput(
            data_alteracao=date(2026, 5, 1),
            novo_salario=Decimal("4500"),
            motivo_alteracao="reajuste",
        )
        p = gerar_s2206_alteracao_contrato(EMP, TRAB, inp)
        alt = p["alt_contratual"]
        assert isinstance(alt, dict)
        assert alt["tpAltContratual"] == "2"
        contrato = alt["infoContrato"]
        assert isinstance(contrato, dict)
        assert "nmCargo" not in contrato
        assert "qtdHrsSem" not in contrato
        assert contrato["vrSalFx"] == "4500"

    def test_motivo_desconhecido_cai_em_outras(self) -> None:
        inp = AlteracaoContratoInput(
            data_alteracao=date(2026, 5, 1),
            novo_cargo="X",
            motivo_alteracao="nada-disso",
        )
        p = gerar_s2206_alteracao_contrato(EMP, TRAB, inp)
        alt = p["alt_contratual"]
        assert isinstance(alt, dict)
        assert alt["tpAltContratual"] == "9"  # outras


# ── S-2230 — Afastamento ───────────────────────────────────────────────────


class TestS2230:
    def test_inicio_doenca_sem_data_fim(self) -> None:
        inp = AfastamentoInput(
            data_inicio=date(2026, 2, 10),
            motivo="doenca",
        )
        p = gerar_s2230_afastamento(EMP, TRAB, inp)
        _common(p, "S-2230")
        info = p["infoAfastamento"]
        assert isinstance(info, dict)
        assert info == {
            "dtIniAfast": "2026-02-10",
            "codMotAfast": "01",
        }
        # Sem fim — não aparece bloco fimAfastamento.
        assert "fimAfastamento" not in info

    def test_afastamento_acidente_trabalho_com_fim(self) -> None:
        inp = AfastamentoInput(
            data_inicio=date(2026, 1, 5),
            data_fim=date(2026, 2, 5),
            motivo="acidente_trabalho",
        )
        p = gerar_s2230_afastamento(EMP, TRAB, inp)
        info = p["infoAfastamento"]
        assert isinstance(info, dict)
        assert info["codMotAfast"] == "03"
        fim = info["fimAfastamento"]
        assert isinstance(fim, dict)
        assert fim == {"dtTermAfast": "2026-02-05"}

    def test_motivo_desconhecido_99(self) -> None:
        inp = AfastamentoInput(
            data_inicio=date(2026, 1, 5),
            motivo="motivo_super_raro",
        )
        p = gerar_s2230_afastamento(EMP, TRAB, inp)
        info = p["infoAfastamento"]
        assert isinstance(info, dict)
        assert info["codMotAfast"] == "99"


# ── S-2298 — Reintegração ──────────────────────────────────────────────────


class TestS2298:
    def test_reintegracao_judicial(self) -> None:
        inp = ReintegracaoInput(
            data_efetiva_retorno=date(2026, 3, 1),
            data_efeitos_financeiros=date(2025, 12, 1),
            tipo_reintegracao="reint_judicial",
            numero_processo="0001234-56.2024.5.02.0001",
        )
        p = gerar_s2298_reintegracao(EMP, TRAB, inp)
        _common(p, "S-2298")
        info = p["infoReintegr"]
        assert isinstance(info, dict)
        assert info["tpReint"] == "1"
        assert info["nrProcJud"] == "0001234-56.2024.5.02.0001"
        assert info["dtEfeitos"] == "2025-12-01"
        assert info["dtEfetRetorno"] == "2026-03-01"

    def test_anistia_legal_sem_processo(self) -> None:
        inp = ReintegracaoInput(
            data_efetiva_retorno=date(2026, 3, 1),
            data_efeitos_financeiros=date(2026, 3, 1),
            tipo_reintegracao="reint_anistia",
        )
        p = gerar_s2298_reintegracao(EMP, TRAB, inp)
        info = p["infoReintegr"]
        assert isinstance(info, dict)
        assert info["tpReint"] == "2"
        assert info["nrProcJud"] is None


# ── S-3000 — Exclusão ──────────────────────────────────────────────────────


class TestS3000:
    def test_exclusao_S1200(self) -> None:
        inp = ExclusaoInput(
            tipo_evento_excluido="S-1200",
            nrRecibo_evento_excluido="1.2.0000000000000123456",
        )
        p = gerar_s3000_exclusao(EMP, inp)
        _common(p, "S-3000")
        # S-3000 não tem ide_trabalhador (exclusão é por chave do recibo).
        assert "ide_vinculo" not in p
        assert "ide_trabalhador" not in p
        info = p["infoExclusao"]
        assert isinstance(info, dict)
        assert info == {
            "tpEvento": "S-1200",
            "nrRecEvt": "1.2.0000000000000123456",
        }

    def test_exclusao_S2299_padrao_rescisao(self) -> None:
        inp = ExclusaoInput(
            tipo_evento_excluido="S-2299",
            nrRecibo_evento_excluido="REC-000-001",
        )
        p = gerar_s3000_exclusao(EMP, inp)
        info = p["infoExclusao"]
        assert isinstance(info, dict)
        assert info["tpEvento"] == "S-2299"


# ── Versão de algoritmo ─────────────────────────────────────────────────────


def test_algoritmo_versao_v3_para_eventos_novos() -> None:
    """Sprint 19.7 PR2 bumpa skeleton.v2 → skeleton.v3."""
    assert ALGORITMO_VERSAO == "esocial.skeleton.v3"
