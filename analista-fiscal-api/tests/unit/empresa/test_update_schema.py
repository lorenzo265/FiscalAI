"""Unit tests do schema de edição de empresa (``EmpresaUpdateIn``).

Cobre as garantias do contrato do PUT: CNPJ não é aceito (identidade imutável),
campos omitidos não entram no ``exclude_unset``, e os validadores de formato.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.empresa.schemas import EmpresaUpdateIn, RegimeTributario


def test_payload_vazio_nao_marca_nenhum_campo() -> None:
    payload = EmpresaUpdateIn()
    assert payload.model_dump(exclude_unset=True) == {}


def test_exclude_unset_so_traz_o_que_foi_enviado() -> None:
    payload = EmpresaUpdateIn.model_validate({"razao_social": "Nova Razão Ltda"})
    assert payload.model_dump(exclude_unset=True) == {"razao_social": "Nova Razão Ltda"}


def test_uf_normalizada_para_maiuscula() -> None:
    payload = EmpresaUpdateIn.model_validate({"uf": "sp"})
    assert payload.uf == "SP"


def test_cnpj_e_rejeitado_extra_forbid() -> None:
    """CNPJ é identidade imutável — não pode ser editado via PUT."""
    with pytest.raises(ValidationError):
        EmpresaUpdateIn.model_validate({"cnpj": "11222333000181"})


def test_campos_de_controle_sao_rejeitados() -> None:
    for campo in ("id", "tenant_id", "ativa", "aliquota_iss_validada", "perfil_ui"):
        with pytest.raises(ValidationError):
            EmpresaUpdateIn.model_validate({campo: "x"})


def test_codigo_ibge_formato_invalido() -> None:
    with pytest.raises(ValidationError):
        EmpresaUpdateIn.model_validate({"codigo_municipio_ibge": "355030"})  # 6 díg


def test_codigo_ibge_valido() -> None:
    payload = EmpresaUpdateIn.model_validate({"codigo_municipio_ibge": "3550308"})
    assert payload.codigo_municipio_ibge == "3550308"


def test_faturamento_negativo_rejeitado() -> None:
    with pytest.raises(ValidationError):
        EmpresaUpdateIn.model_validate({"faturamento_12m": "-1"})


def test_razao_social_curta_rejeitada() -> None:
    with pytest.raises(ValidationError):
        EmpresaUpdateIn.model_validate({"razao_social": "ab"})


def test_regime_aceita_enum() -> None:
    payload = EmpresaUpdateIn.model_validate({"regime_tributario": "lucro_presumido"})
    assert payload.regime_tributario is RegimeTributario.LUCRO_PRESUMIDO


def test_regime_invalido_rejeitado() -> None:
    with pytest.raises(ValidationError):
        EmpresaUpdateIn.model_validate({"regime_tributario": "lucro_irreal"})
