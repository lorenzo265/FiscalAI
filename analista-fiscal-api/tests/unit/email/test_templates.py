"""Golden dos templates de e-mail (Marco 4 PR3 #14).

Funções puras — sem I/O. Cobre: assunto, render HTML+texto, formatação
de moeda pt-BR, escape XSS, e ``to`` vazio (caller preenche).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.shared.integrations.email.templates import (
    _brl,
    renderizar_alerta_fiscal,
    renderizar_fatura,
    renderizar_onboarding,
)
from app.shared.integrations.email.types import TipoEmail


def test_brl_formata_milhar_e_centavos() -> None:
    assert _brl(Decimal("1234.5")) == "R$ 1.234,50"
    assert _brl(Decimal("10000.00")) == "R$ 10.000,00"
    assert _brl(Decimal("0.99")) == "R$ 0,99"
    assert _brl(Decimal("1234567.89")) == "R$ 1.234.567,89"


def test_onboarding_estrutura() -> None:
    msg = renderizar_onboarding(nome="Ana", link_painel="https://app.arkan.com.br")
    assert msg.assunto == "Bem-vindo ao Arkan, Ana"
    assert msg.to == ""  # caller preenche
    assert "Olá, Ana" in msg.html
    assert "https://app.arkan.com.br" in msg.html
    assert "Olá, Ana" in msg.texto
    assert "<" not in msg.texto  # fallback texto é plain
    assert msg.tags == (TipoEmail.ONBOARDING.value,)


def test_fatura_mostra_valor_e_vencimento() -> None:
    msg = renderizar_fatura(
        nome="João",
        plano="Profissional",
        valor=Decimal("299.00"),
        vencimento=date(2026, 7, 10),
        link_pagamento="https://pay.arkan.com.br/x",
    )
    assert msg.assunto == "Sua fatura Arkan — Profissional"
    assert "R$ 299,00" in msg.html
    assert "R$ 299,00" in msg.texto
    assert "10/07/2026" in msg.html
    assert "10/07/2026" in msg.texto
    assert msg.tags == (TipoEmail.FATURA.value,)


def test_alerta_fiscal_com_e_sem_prazo() -> None:
    com = renderizar_alerta_fiscal(
        nome="Ana",
        titulo="Sua guia do mês está pronta",
        mensagem="A guia de impostos de junho já pode ser paga.",
        link_painel="https://app.arkan.com.br",
        prazo=date(2026, 7, 20),
    )
    assert com.assunto == "Arkan: Sua guia do mês está pronta"
    assert "20/07/2026" in com.html
    assert "20/07/2026" in com.texto

    sem = renderizar_alerta_fiscal(
        nome="Ana",
        titulo="Tudo em dia",
        mensagem="Nenhuma pendência neste mês.",
        link_painel="https://app.arkan.com.br",
    )
    assert "Prazo" not in sem.html
    assert "Prazo" not in sem.texto


def test_escape_xss_no_nome() -> None:
    msg = renderizar_onboarding(
        nome="<script>alert(1)</script>", link_painel="https://x"
    )
    assert "<script>" not in msg.html
    assert "&lt;script&gt;" in msg.html
