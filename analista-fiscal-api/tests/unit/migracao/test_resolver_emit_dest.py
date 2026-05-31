"""Testes do helper ``_resolver_emit_dest`` (Sprint 19.7 PR3 #36)."""

from __future__ import annotations

from app.modules.migracao.service import (
    _resolver_emit_dest,
    tenant_cnpj_placeholder,
)


# ── Saída — empresa emite ──────────────────────────────────────────────────


def test_saida_canonica_empresa_emite_participante_recebe() -> None:
    emit, dest = _resolver_emit_dest(
        "saida",
        cnpj_empresa="11222333000144",
        cnpj_participante="99887766000155",
    )
    assert emit == "11222333000144"
    assert dest == "99887766000155"


def test_saida_b2c_destinatario_none() -> None:
    """NFC-e venda B2C: cliente vem como `(00)` ou sem 0150 → dest None."""
    emit, dest = _resolver_emit_dest(
        "saida",
        cnpj_empresa="11222333000144",
        cnpj_participante=None,
    )
    assert emit == "11222333000144"
    assert dest is None


def test_saida_sem_cnpj_empresa_cai_em_placeholder() -> None:
    """Arquivo SPED estruturalmente quebrado (sem 0000): fall-back."""
    emit, dest = _resolver_emit_dest(
        "saida",
        cnpj_empresa=None,
        cnpj_participante="99887766000155",
    )
    assert emit == tenant_cnpj_placeholder()
    assert dest == "99887766000155"


# ── Entrada — fornecedor emite ─────────────────────────────────────────────


def test_entrada_canonica_fornecedor_emite() -> None:
    emit, dest = _resolver_emit_dest(
        "entrada",
        cnpj_empresa="11222333000144",
        cnpj_participante="99887766000155",
    )
    assert emit == "99887766000155"
    assert dest == "11222333000144"


def test_entrada_fornecedor_sem_cnpj_cai_em_placeholder() -> None:
    """0150 com COD_PART → (None, CPF) — emite vira placeholder, não vaza CPF."""
    emit, dest = _resolver_emit_dest(
        "entrada",
        cnpj_empresa="11222333000144",
        cnpj_participante=None,
    )
    assert emit == tenant_cnpj_placeholder()
    assert dest == "11222333000144"


def test_direcao_desconhecida_trata_como_entrada_fail_safe() -> None:
    """Defesa em profundidade: direção bizarra cai no caminho 'entrada'."""
    emit, dest = _resolver_emit_dest(
        "qualquercoisa",
        cnpj_empresa="11222333000144",
        cnpj_participante="99887766000155",
    )
    # Tratado como entrada (caso 'else') — emitente é o participante.
    assert emit == "99887766000155"
    assert dest == "11222333000144"


def test_placeholder_continua_disponivel_para_legado() -> None:
    """tenant_cnpj_placeholder() permanece como hook pra compatibilidade."""
    assert tenant_cnpj_placeholder() == "00000000000000"
