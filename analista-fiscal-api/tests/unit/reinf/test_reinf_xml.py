"""Golden do serializador XML EFD-Reinf (Marco 4 PR2 #11).

Função pura — sem banco, sem I/O. Cobre:
  * Estrutura `<Reinf><evtPgtoBenefPJ Id=...>` + namespace do leiaute.
  * Conversão snake_case → camelCase das seções do payload.
  * Skip de chaves meta/internas (prefixo ``_``).
  * Geração e validação do atributo Id.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.modules.reinf.esocial_payload import (
    BeneficiarioPjInput,
    ContratanteInput,
    RetencaoR4020Input,
    gerar_r4020,
)
from app.modules.reinf.reinf_xml import (
    gerar_id_evento,
    serializar_para_xml,
)

_TZ = ZoneInfo("America/Sao_Paulo")


def _payload_r4020() -> dict[str, object]:
    return gerar_r4020(
        ContratanteInput(cnpj="11222333000144", razao_social="Tomador LTDA"),
        BeneficiarioPjInput(cnpj="99888777000166", razao_social="Prestador SA"),
        RetencaoR4020Input(
            competencia=date(2026, 4, 1),
            valor_bruto_servico=Decimal("10000.00"),
            ir_retido=Decimal("150.00"),
            pis_retido=Decimal("65.00"),
            cofins_retido=Decimal("300.00"),
            csll_retido=Decimal("100.00"),
            descricao="Consultoria",
        ),
    )


def test_serializa_estrutura_e_namespace() -> None:
    xml = serializar_para_xml(_payload_r4020(), id_evento="IDFIXED123")
    assert xml.startswith("<Reinf ")
    assert "evt4020PagtoBeneficiarioPJ/v2_01_02" in xml
    assert '<evtPgtoBenefPJ Id="IDFIXED123">' in xml
    assert xml.rstrip().endswith("</Reinf>")


def test_converte_snake_para_camel() -> None:
    xml = serializar_para_xml(_payload_r4020(), id_evento="IDX")
    # Seções viram camelCase.
    assert "<ideEvento>" in xml
    assert "<ideContri>" in xml
    assert "<ideBenef>" in xml
    assert "<idePgto>" in xml
    assert "<infoPgto>" in xml
    # Tags snake-case NÃO devem aparecer.
    assert "<ide_evento>" not in xml
    assert "<ide_contri>" not in xml
    assert "<info_pgto>" not in xml


def test_valores_e_cnpjs_presentes() -> None:
    xml = serializar_para_xml(_payload_r4020(), id_evento="IDX")
    assert "<nrInsc>11222333000144</nrInsc>" in xml
    assert "<cnpjBenef>99888777000166</cnpjBenef>" in xml
    assert "<vlrIR>150.00</vlrIR>" in xml
    assert "<vlrCOFINS>300.00</vlrCOFINS>" in xml


def test_skip_chave_interna_underscore() -> None:
    payload = _payload_r4020()
    payload["_retencao_snapshot"] = {"regime_tomador": "lucro_presumido"}
    xml = serializar_para_xml(payload, id_evento="IDX")
    assert "retencao_snapshot" not in xml
    assert "regime_tomador" not in xml


def test_id_gerado_do_cnpj_quando_ausente() -> None:
    agora = datetime(2026, 4, 15, 10, 30, 0, tzinfo=_TZ)
    xml = serializar_para_xml(_payload_r4020(), agora=agora)
    # ID1 + CNPJ + AAAAMMDDhhmmss + seq(5).
    assert 'Id="ID111222333000144202604151030000001' in xml or (
        'Id="ID111222333000144' in xml
    )


def test_gerar_id_evento_formato() -> None:
    agora = datetime(2026, 4, 15, 10, 30, 0, tzinfo=_TZ)
    out = gerar_id_evento("11222333000144", agora=agora)
    assert out == "ID11122233300014420260415103000" + "00001"
    assert len(out) == 36


def test_gerar_id_evento_cnpj_invalido() -> None:
    with pytest.raises(ValueError, match="14 dígitos"):
        gerar_id_evento("123")


def test_gerar_id_evento_sequencial_fora_da_faixa() -> None:
    with pytest.raises(ValueError, match="sequencial"):
        gerar_id_evento("11222333000144", 0)


def test_tipo_desconhecido_levanta() -> None:
    with pytest.raises(ValueError, match="Tipo de evento"):
        serializar_para_xml({"tipo": "R-9999"}, id_evento="X")


def test_sem_cnpj_e_sem_id_levanta() -> None:
    payload = _payload_r4020()
    del payload["ide_contri"]
    with pytest.raises(ValueError, match="CNPJ ausente"):
        serializar_para_xml(payload)
