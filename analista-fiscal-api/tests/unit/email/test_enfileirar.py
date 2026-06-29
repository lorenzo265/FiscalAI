"""Marco 4 PR3 (#14) — dispatch helper ``enfileirar_email``.

Garante que os fluxos (onboarding/fatura/alerta) chamam a task ``email.enviar``
com o destinatário real + o corpo JÁ renderizado pelo template. Não toca DB nem
Celery: faz patch em ``enqueue`` (que é no-op sem broker).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from app.shared.integrations.email.templates import (
    renderizar_alerta_fiscal,
    renderizar_fatura,
    renderizar_onboarding,
)
from app.workers.tasks.email_enviar import enfileirar_email


def test_enfileirar_despacha_corpo_renderizado_e_destinatario() -> None:
    msg = renderizar_onboarding(nome="Maria", link_painel="http://app.local")
    with patch("app.workers.tasks.email_enviar.enqueue") as mock_enqueue:
        enfileirar_email(msg, to="maria@empresa.com.br", tags=["onboarding"])

    assert mock_enqueue.call_count == 1
    _args, kwargs = mock_enqueue.call_args
    assert kwargs["to"] == "maria@empresa.com.br"  # `to` real, não o vazio do template
    assert kwargs["tags"] == ["onboarding"]
    assert kwargs["assunto"] == msg.assunto
    assert kwargs["html"] == msg.html
    assert kwargs["texto"] == msg.texto


def test_enfileirar_fatura_tem_valor_no_corpo() -> None:
    msg = renderizar_fatura(
        nome="João",
        plano="essencial",
        valor=Decimal("149.00"),
        vencimento=date(2026, 7, 1),
        link_pagamento="http://app.local/configuracoes",
    )
    with patch("app.workers.tasks.email_enviar.enqueue") as mock_enqueue:
        enfileirar_email(msg, to="joao@empresa.com.br", tags=["fatura"])

    assert mock_enqueue.call_count == 1
    _args, kwargs = mock_enqueue.call_args
    assert kwargs["tags"] == ["fatura"]
    # Moeda pt-BR no corpo (149,00) — não vaza Decimal cru.
    assert "149,00" in kwargs["html"]


def test_enfileirar_alerta_traduz_sem_jargao() -> None:
    msg = renderizar_alerta_fiscal(
        nome="Ana",
        titulo="DAS de junho",
        mensagem="Sua guia do mês vence em breve.",
        link_painel="http://app.local/compliance",
        prazo=date(2026, 7, 20),
    )
    with patch("app.workers.tasks.email_enviar.enqueue") as mock_enqueue:
        enfileirar_email(msg, to="ana@empresa.com.br", tags=["alerta_fiscal"])

    assert mock_enqueue.call_count == 1
    _args, kwargs = mock_enqueue.call_args
    assert kwargs["tags"] == ["alerta_fiscal"]
    assert "DAS de junho" in kwargs["html"]
