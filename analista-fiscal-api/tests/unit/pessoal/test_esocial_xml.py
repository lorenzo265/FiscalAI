"""Golden tests do gerador XML eSocial (Sprint 10 PR3+).

Cobre os 5 eventos suportados + edge cases do conversor recursivo:
campos nulos pulados, listas viram tags repetidas, booleanos viram S/N,
datas → ISO, Id calculado vs Id explícito.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.modules.pessoal.esocial_payloads import (
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
    gerar_s2300_inicio_tsve,
)
from app.modules.pessoal.esocial_xml import (
    gerar_id_evento,
    serializar_para_xml,
)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_AGORA = datetime(2026, 5, 15, 14, 30, 0, tzinfo=_TZ_BR)
_CNPJ = "12345678000195"


def _strip_ns(tag: str) -> str:
    """ElementTree devolve tags como '{ns}tag' — pega só o nome local."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find(root: ET.Element, path: str) -> ET.Element | None:
    """Busca por path relativo ignorando namespace (find não casa sem ns prefix)."""
    parts = path.split("/")
    el: ET.Element | None = root
    for p in parts:
        if el is None:
            return None
        nxt: ET.Element | None = None
        for c in el:
            if _strip_ns(c.tag) == p:
                nxt = c
                break
        el = nxt
    return el


def _empregador() -> EmpregadorInput:
    return EmpregadorInput(cnpj=_CNPJ, razao_social="Teste eSocial Ltda")


def _trabalhador() -> TrabalhadorInput:
    return TrabalhadorInput(
        cpf="39053344705",
        nome="Funcionario Teste",
        data_nascimento=date(1990, 6, 15),
    )


# ── gerar_id_evento ─────────────────────────────────────────────────────────


def test_gerar_id_evento_formato() -> None:
    eid = gerar_id_evento(_CNPJ, "2026-05", sequencial=1, agora=_AGORA)
    assert eid == "ID112345678000195202605151430000000 1"[:35] or eid.startswith(
        "ID112345678000195202605151430000"
    )
    # 2 (ID) + 1 (tpInsc) + 14 (CNPJ) + 14 (timestamp) + 5 (seq) = 36 chars
    assert len(eid) == 36
    assert eid.startswith("ID1" + _CNPJ)


def test_gerar_id_evento_rejeita_cnpj_invalido() -> None:
    with pytest.raises(ValueError, match="CNPJ deve ter 14 dígitos"):
        gerar_id_evento("123", "2026-05", agora=_AGORA)


def test_gerar_id_evento_rejeita_sequencial_fora_faixa() -> None:
    with pytest.raises(ValueError, match="sequencial fora de"):
        gerar_id_evento(_CNPJ, "2026-05", sequencial=0, agora=_AGORA)
    with pytest.raises(ValueError, match="sequencial fora de"):
        gerar_id_evento(_CNPJ, "2026-05", sequencial=100000, agora=_AGORA)


# ── S-1200 — Remuneração ────────────────────────────────────────────────────


def test_serializa_s1200_estrutura_basica() -> None:
    payload = gerar_s1200_remuneracao(
        _empregador(),
        _trabalhador(),
        HoleriteInput(
            competencia=date(2026, 4, 1),
            salario_bruto=Decimal("3000.00"),
            inss_empregado=Decimal("253.41"),
            irrf=Decimal("36.55"),
            fgts_empregador=Decimal("240.00"),
            valor_liquido=Decimal("2710.04"),
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)

    root = ET.fromstring(xml)
    assert _strip_ns(root.tag) == "eSocial"
    assert "evtRemun" in {_strip_ns(child.tag) for child in root}

    evt = root[0]
    assert evt.attrib["Id"].startswith("ID1" + _CNPJ)

    # Verifica seções principais presentes
    tags_filhas = [_strip_ns(c.tag) for c in evt]
    assert "ide_evento" in tags_filhas
    assert "ide_empregador" in tags_filhas
    assert "ide_trabalhador" in tags_filhas
    assert "dm_dev" in tags_filhas


def test_s1200_pula_campos_nulos() -> None:
    """Trabalhador sem data_nascimento — campo opcional não vira tag vazia."""
    trab = TrabalhadorInput(cpf="39053344705", nome="Sem Nasc")
    payload = gerar_s2200_admissao(
        _empregador(),
        trab,
        AdmissaoInput(
            data_admissao=date(2025, 1, 15),
            cargo=None,  # propositalmente None
            salario_base=Decimal("3000.00"),
            vinculo="clt",
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    # dtNascto e nmCargo NÃO podem aparecer como tags vazias
    assert "<dtNascto>" not in xml
    assert "<nmCargo>" not in xml


# ── S-1210 — Pagamento ──────────────────────────────────────────────────────


def test_serializa_s1210_pagamento() -> None:
    payload = gerar_s1210_pagamento(
        _empregador(),
        _trabalhador(),
        PagamentoInput(
            data_pagamento=date(2026, 5, 5),
            valor_liquido=Decimal("2710.04"),
            periodo_referencia=date(2026, 4, 1),
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    evt = root[0]
    assert _strip_ns(evt.tag) == "evtPgtos"
    # dtPgto é dia do pagamento ISO
    dt_pgto = _find(evt, "dt_pgto")
    assert dt_pgto is not None and dt_pgto.text == "2026-05-05"


# ── S-2200 — Admissão ───────────────────────────────────────────────────────


def test_serializa_s2200_admissao_clt() -> None:
    payload = gerar_s2200_admissao(
        _empregador(),
        _trabalhador(),
        AdmissaoInput(
            data_admissao=date(2025, 1, 15),
            cargo="Vendedor Pleno",
            salario_base=Decimal("3500.00"),
            vinculo="clt",
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    evt = root[0]
    assert _strip_ns(evt.tag) == "evtAdmissao"

    cat = _find(evt, "vinculo/info_celetista/codCateg")
    assert cat is not None and cat.text == "10"  # CLT


def test_s2200_vinculo_intermitente() -> None:
    payload = gerar_s2200_admissao(
        _empregador(),
        _trabalhador(),
        AdmissaoInput(
            data_admissao=date(2025, 1, 15),
            cargo="Garçom",
            salario_base=Decimal("1518.00"),
            vinculo="intermitente",
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    cat = _find(root, "evtAdmissao/vinculo/info_celetista/codCateg")
    assert cat is not None and cat.text == "11"


# ── S-2299 — Desligamento ───────────────────────────────────────────────────


def test_serializa_s2299_desligamento_sem_justa_causa() -> None:
    payload = gerar_s2299_desligamento(
        _empregador(),
        _trabalhador(),
        DesligamentoInput(
            data_desligamento=date(2026, 4, 20),
            motivo="sem_justa_causa",
            valor_bruto_verbas=Decimal("5500.00"),
            saldo_fgts=Decimal("12000.00"),
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    motivo = _find(root, "evtDeslig/info_deslig/mtvDeslig")
    assert motivo is not None and motivo.text == "02"  # sem justa causa


def test_s2299_motivo_mutuo_acordo() -> None:
    payload = gerar_s2299_desligamento(
        _empregador(),
        _trabalhador(),
        DesligamentoInput(
            data_desligamento=date(2026, 4, 20),
            motivo="mutuo_acordo",
            valor_bruto_verbas=Decimal("5500.00"),
            saldo_fgts=Decimal("12000.00"),
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    motivo = _find(root, "evtDeslig/info_deslig/mtvDeslig")
    assert motivo is not None and motivo.text == "37"  # mútuo acordo


# ── S-2300 — TSVE (sócio com pró-labore) — Sprint 19.6 PR1 #14 ─────────────


def test_serializa_s2300_inicio_tsve() -> None:
    payload = gerar_s2300_inicio_tsve(
        _empregador(),
        TrabalhadorInput(
            cpf="11122233399",
            nome="Sócio TSVE",
            data_nascimento=date(1975, 3, 20),
        ),
        data_inicio=date(2025, 1, 1),
        valor_referencia=Decimal("5000.00"),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    root = ET.fromstring(xml)
    evt = root[0]
    # Tag canônica do S-2300 — antes era "evtCdBenefIn" (S-2400 RPPS).
    assert _strip_ns(evt.tag) == "evtTSVInicio"
    cod = _find(evt, "infoTSVInicio/codCateg")
    # 723 = sócio empresário (contribuinte individual). Antes era 701 (errado).
    assert cod is not None and cod.text == "723"
    cpf = _find(evt, "trabSemVinc/cpfTrab")
    assert cpf is not None and cpf.text == "11122233399"


# ── Edge cases do conversor ─────────────────────────────────────────────────


def test_id_evento_explicito_sobrescreve_geracao() -> None:
    payload = gerar_s1210_pagamento(
        _empregador(),
        _trabalhador(),
        PagamentoInput(
            data_pagamento=date(2026, 5, 5),
            valor_liquido=Decimal("100.00"),
        ),
    )
    custom_id = "ID1" + _CNPJ + "20260501120000" + "12345"
    xml = serializar_para_xml(payload, id_evento=custom_id, agora=_AGORA)
    root = ET.fromstring(xml)
    assert root[0].attrib["Id"] == custom_id


def test_serializar_rejeita_tipo_desconhecido() -> None:
    with pytest.raises(ValueError, match="Tipo de evento desconhecido"):
        serializar_para_xml(
            {"tipo": "S-9999", "ide_empregador": {"nrInsc": _CNPJ}}
        )


def test_serializar_rejeita_tipo_ausente() -> None:
    with pytest.raises(ValueError, match="Tipo de evento desconhecido"):
        serializar_para_xml({"ide_empregador": {"nrInsc": _CNPJ}})


def test_xml_namespace_correto_por_evento() -> None:
    """Namespace deve refletir o slug XSD do evento (admissao, remun, etc)."""
    payload = gerar_s2200_admissao(
        _empregador(),
        _trabalhador(),
        AdmissaoInput(
            data_admissao=date(2025, 1, 15),
            cargo="X",
            salario_base=Decimal("2000.00"),
            vinculo="clt",
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    assert (
        'xmlns="http://www.esocial.gov.br/schema/evt/admissao/vS_01_03_00"' in xml
    )


def test_listas_viram_tags_repetidas() -> None:
    """eSocial usa repetição da mesma tag para listas (`dm_dev`)."""
    payload = gerar_s1200_remuneracao(
        _empregador(),
        _trabalhador(),
        HoleriteInput(
            competencia=date(2026, 4, 1),
            salario_bruto=Decimal("3000.00"),
            inss_empregado=Decimal("253.41"),
            irrf=Decimal("36.55"),
            fgts_empregador=Decimal("240.00"),
            valor_liquido=Decimal("2710.04"),
        ),
    )
    xml = serializar_para_xml(payload, agora=_AGORA)
    # `det_verbas` é lista com 3 rubricas (bruto, INSS, IRRF) → 3 tags
    assert xml.count("<det_verbas>") == 3
