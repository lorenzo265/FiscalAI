"""Testes do renderer de holerite (Sprint 19.6 PR4 #11)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4


def _holerite(**over: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": UUID("11111111-1111-1111-1111-111111111111"),
        "tenant_id": UUID("22222222-2222-2222-2222-222222222222"),
        "folha_mensal_id": UUID("33333333-3333-3333-3333-333333333333"),
        "funcionario_id": uuid4(),
        "competencia": date(2026, 5, 1),
        "salario_base": Decimal("3000.00"),
        "salario_bruto": Decimal("3000.00"),
        "inss_empregado": Decimal("267.32"),
        "inss_aliquota_efetiva": Decimal("0.0891"),
        "dependentes_irrf": 0,
        "deducao_dependentes_irrf": Decimal("0"),
        "base_irrf": Decimal("2732.68"),
        "irrf": Decimal("0"),
        "irrf_faixa": 1,
        "fgts_empregador": Decimal("240.00"),
        "fgts_aliquota": Decimal("0.08"),
        "valor_liquido": Decimal("2732.68"),
        "algoritmo_versao": "pessoal.holerite.v2",
    }
    base.update(over)
    return SimpleNamespace(**base)


def _funcionario(**over: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "nome": "João da Silva",
        "cpf": "12345678901",
        "cargo": "Analista Fiscal",
        "vinculo": "clt",
    }
    base.update(over)
    return SimpleNamespace(**base)


# ── Renderer texto ────────────────────────────────────────────────────────


def test_renderiza_holerite_basico() -> None:
    from app.modules.pessoal.renderer_holerite import renderizar_holerite_texto

    bytes_out = renderizar_holerite_texto(
        _holerite(),
        _funcionario(),
        empresa_nome="ACME Comércio LTDA",
    )
    texto = bytes_out.decode("utf-8")
    assert "Holerite — ACME Comércio LTDA" in texto
    assert "Maio/2026" in texto
    assert "João da Silva" in texto
    assert "123.456.789-01" in texto
    assert "Analista Fiscal" in texto
    assert "Salário Bruto: R$ 3000.00" in texto
    assert "INSS  8.91%" in texto
    assert "R$ 267.32" in texto
    assert "Líquido a Receber: R$ 2732.68" in texto
    assert "FGTS (empregador): R$ 240.00" in texto
    assert "Algoritmo: pessoal.holerite.v2" in texto


def test_renderiza_sem_cargo_omite_linha() -> None:
    from app.modules.pessoal.renderer_holerite import renderizar_holerite_texto

    texto = renderizar_holerite_texto(
        _holerite(),
        _funcionario(cargo=None),
        empresa_nome="X",
    ).decode("utf-8")
    assert "Cargo:" not in texto


def test_renderiza_com_irrf_inclui_desconto() -> None:
    """IRRF > 0 aparece na seção Descontos."""
    from app.modules.pessoal.renderer_holerite import renderizar_holerite_texto

    h = _holerite(irrf=Decimal("125.50"))
    texto = renderizar_holerite_texto(
        h, _funcionario(), empresa_nome="X"
    ).decode("utf-8")
    assert "IRRF: R$ 125.50" in texto


def test_renderiza_sem_irrf_omite_desconto() -> None:
    """IRRF == 0 não polui o texto."""
    from app.modules.pessoal.renderer_holerite import renderizar_holerite_texto

    texto = renderizar_holerite_texto(
        _holerite(irrf=Decimal("0")), _funcionario(), empresa_nome="X"
    ).decode("utf-8")
    assert "IRRF" not in texto.split("─ Resumo ─")[0].split("─ Descontos ─")[1]


def test_cpf_invalido_passa_como_esta() -> None:
    from app.modules.pessoal.renderer_holerite import renderizar_holerite_texto

    texto = renderizar_holerite_texto(
        _holerite(),
        _funcionario(cpf="123"),
        empresa_nome="X",
    ).decode("utf-8")
    assert "CPF: 123" in texto  # sem formatação se inválido


# ── Chave storage ─────────────────────────────────────────────────────────


def test_chave_storage_prefixa_tenant_empresa() -> None:
    from app.modules.pessoal.renderer_holerite import chave_storage_holerite

    h = _holerite()
    chave = chave_storage_holerite(h)
    assert chave.startswith("tenant/")
    assert "22222222-2222-2222-2222-222222222222" in chave
    assert "holerite/2026-05-01" in chave
    assert chave.endswith(".md")


def test_chave_storage_determinista() -> None:
    """Mesmo holerite → mesma chave (idempotência §8.9)."""
    from app.modules.pessoal.renderer_holerite import chave_storage_holerite

    h = _holerite()
    assert chave_storage_holerite(h) == chave_storage_holerite(h)
