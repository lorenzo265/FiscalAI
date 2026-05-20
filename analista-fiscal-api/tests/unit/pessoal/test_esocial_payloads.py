"""Testes dos geradores skeleton de payloads eSocial (Sprint 10 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.pessoal.esocial_payloads import (
    ALGORITMO_VERSAO,
    AdmissaoInput,
    DesligamentoInput,
    EmpregadorInput,
    HoleriteInput,
    PagamentoInput,
    TrabalhadorInput,
    gerar_s1200_remuneracao,
    gerar_s1210_pagamento,
    gerar_s2200_admissao,
    gerar_s2299_desligamento,
    gerar_s2400_beneficiario,
)

EMP = EmpregadorInput(cnpj="12345678000190", razao_social="Acme LTDA")
TRAB = TrabalhadorInput(
    cpf="11122233344", nome="Maria Souza",
    data_nascimento=date(1990, 5, 12),
)


def _bloco_comum(payload: dict, tipo: str) -> None:
    assert payload["tipo"] == tipo
    assert payload["versao_leiaute"] == "S-1.3"
    assert payload["algoritmo_versao"] == ALGORITMO_VERSAO
    assert payload["ide_empregador"] == {
        "tpInsc": 1, "nrInsc": "12345678000190",
    }


class TestS1200:
    def test_estrutura(self) -> None:
        hol = HoleriteInput(
            competencia=date(2026, 1, 1),
            salario_bruto=Decimal("3000"),
            inss_empregado=Decimal("253.41"),
            irrf=Decimal("36.55"),
            fgts_empregador=Decimal("240"),
            valor_liquido=Decimal("2710.04"),
        )
        p = gerar_s1200_remuneracao(EMP, TRAB, hol)
        _bloco_comum(p, "S-1200")
        assert p["ide_evento"]["perApur"] == "2026-01"
        assert p["ide_trabalhador"]["cpfTrab"] == "11122233344"
        # Rubricas: salário bruto + INSS + IRRF
        rubricas = p["dm_dev"][0]["info_per_apur"]["ide_estab_lot"][0]["det_verbas"]
        assert len(rubricas) == 3
        assert rubricas[0]["vr_rubr"] == "3000"
        assert rubricas[1]["vr_rubr"] == "253.41"
        assert rubricas[2]["vr_rubr"] == "36.55"

    def test_perApur_formato_yyyymm(self) -> None:
        hol = HoleriteInput(
            competencia=date(2026, 12, 1),
            salario_bruto=Decimal("100"),
            inss_empregado=Decimal("0"),
            irrf=Decimal("0"),
            fgts_empregador=Decimal("0"),
            valor_liquido=Decimal("100"),
        )
        p = gerar_s1200_remuneracao(EMP, TRAB, hol)
        assert p["ide_evento"]["perApur"] == "2026-12"


class TestS1210:
    def test_estrutura(self) -> None:
        pag = PagamentoInput(
            data_pagamento=date(2026, 2, 5),
            valor_liquido=Decimal("2710.04"),
            periodo_referencia=date(2026, 1, 1),
        )
        p = gerar_s1210_pagamento(EMP, TRAB, pag)
        _bloco_comum(p, "S-1210")
        assert p["dt_pgto"] == "2026-02-05"
        assert p["info_pgto"]["perRef"] == "2026-01"
        assert p["info_pgto"]["vrLiq"] == "2710.04"
        assert p["ide_benef"]["cpfBenef"] == "11122233344"


class TestS2200:
    def test_admissao_clt(self) -> None:
        adm = AdmissaoInput(
            data_admissao=date(2026, 1, 15),
            cargo="Atendente",
            salario_base=Decimal("3000"),
            vinculo="clt",
        )
        p = gerar_s2200_admissao(EMP, TRAB, adm)
        _bloco_comum(p, "S-2200")
        assert p["vinculo"]["info_celetista"]["codCateg"] == 10
        assert p["vinculo"]["info_celetista"]["dtAdm"] == "2026-01-15"
        assert p["vinculo"]["info_contrato"]["vrSalFx"] == "3000"
        assert p["vinculo"]["info_contrato"]["nmCargo"] == "Atendente"
        assert p["trabalhador"]["dtNascto"] == "1990-05-12"

    def test_admissao_intermitente(self) -> None:
        adm = AdmissaoInput(
            data_admissao=date(2026, 6, 1),
            cargo="Garçom",
            salario_base=Decimal("1518"),
            vinculo="intermitente",
        )
        p = gerar_s2200_admissao(EMP, TRAB, adm)
        assert p["vinculo"]["info_celetista"]["codCateg"] == 11

    def test_admissao_sem_data_nascimento(self) -> None:
        trab = TrabalhadorInput(cpf="00011122233", nome="Ana", data_nascimento=None)
        adm = AdmissaoInput(
            data_admissao=date(2026, 1, 1),
            cargo=None,
            salario_base=Decimal("2000"),
            vinculo="prazo_determinado",
        )
        p = gerar_s2200_admissao(EMP, trab, adm)
        assert p["trabalhador"]["dtNascto"] is None
        assert p["vinculo"]["info_celetista"]["codCateg"] == 20


class TestS2299:
    def test_sem_justa_causa(self) -> None:
        des = DesligamentoInput(
            data_desligamento=date(2026, 5, 15),
            motivo="sem_justa_causa",
            valor_bruto_verbas=Decimal("16400"),
            saldo_fgts=Decimal("8640"),
        )
        p = gerar_s2299_desligamento(EMP, TRAB, des)
        _bloco_comum(p, "S-2299")
        assert p["info_deslig"]["mtvDeslig"] == "02"
        assert p["info_deslig"]["dtDeslig"] == "2026-05-15"
        assert p["info_deslig"]["vlrBrutoVerbas"] == "16400"
        assert p["info_deslig"]["vlrSaldoFGTS"] == "8640"

    @pytest.mark.parametrize(
        "motivo,codigo",
        [
            ("com_justa_causa", "03"),
            ("pedido_demissao", "07"),
            ("mutuo_acordo", "37"),
            ("termino_determinado", "08"),
        ],
    )
    def test_motivos(self, motivo: str, codigo: str) -> None:
        des = DesligamentoInput(
            data_desligamento=date(2026, 3, 31),
            motivo=motivo,
            valor_bruto_verbas=Decimal("0"),
            saldo_fgts=Decimal("0"),
        )
        p = gerar_s2299_desligamento(EMP, TRAB, des)
        assert p["info_deslig"]["mtvDeslig"] == codigo


class TestS2400:
    def test_socio_pro_labore(self) -> None:
        p = gerar_s2400_beneficiario(
            EMP, TRAB,
            data_inicio=date(2026, 1, 1),
            valor_referencia=Decimal("5000"),
        )
        _bloco_comum(p, "S-2400")
        assert p["info_benef"]["codCateg"] == 701
        assert p["info_benef"]["vrReferencia"] == "5000"
        assert p["info_benef"]["dtInicio"] == "2026-01-01"
        assert p["ide_beneficiario"]["cpfBenef"] == "11122233344"
