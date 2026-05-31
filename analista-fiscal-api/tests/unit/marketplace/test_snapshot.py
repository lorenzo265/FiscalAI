"""Tests do snapshot da empresa (Sprint 13 PR2)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from app.modules.marketplace.snapshot import SNAPSHOT_VERSAO, snapshot_empresa


def _empresa(**over: object) -> SimpleNamespace:
    base = {
        "id": uuid.uuid4(),
        "razao_social": "Loja Teste LTDA",
        "nome_fantasia": "Loja Teste",
        "cnpj": "12345678000195",
        "regime_tributario": "simples_nacional",
        "perfil_ui": "sn_sem_funcionarios",
        "anexo_simples": "I",
        "cnae_principal": "4711301",
        "municipio": "São Paulo",
        "uf": "SP",
        "faturamento_12m": Decimal("500000.00"),
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_versao_estavel() -> None:
    assert SNAPSHOT_VERSAO == "v1"


def test_snapshot_serializa_decimal_como_str() -> None:
    snap = snapshot_empresa(_empresa())  # type: ignore[arg-type]
    assert snap["faturamento_12m"] == "500000.00"
    assert isinstance(snap["faturamento_12m"], str)


def test_snapshot_preserva_campos_obrigatorios() -> None:
    snap = snapshot_empresa(_empresa())  # type: ignore[arg-type]
    assert snap["razao_social"] == "Loja Teste LTDA"
    assert snap["cnpj"] == "12345678000195"
    assert snap["regime_tributario"] == "simples_nacional"
    assert snap["uf"] == "SP"


def test_snapshot_faturamento_nulo_vira_none() -> None:
    snap = snapshot_empresa(_empresa(faturamento_12m=None))  # type: ignore[arg-type]
    assert snap["faturamento_12m"] is None
