"""Templates de e-mail transacional — funções puras (Marco 4 PR3 #14).

Camada 1 (determinística): cada função recebe um contexto tipado e devolve
um ``EmailMessage`` com HTML + fallback texto. Zero I/O, golden-testável.

Regra de produto (espelha o frontend): linguagem do **dono de PME**, nunca
jargão fiscal cru. "Sua guia do mês está pronta", não "DAS PGDAS-D apurado".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape

from app.shared.integrations.email.types import EmailMessage, TipoEmail

_COR_VERDE = "#1f6f43"  # verde-marca (saúde fiscal) — único acento
_ASSINATURA = "Equipe Arkan"


def _brl(valor: Decimal) -> str:
    """Formata Decimal como moeda pt-BR: ``Decimal('1234.5')`` → ``R$ 1.234,50``."""
    q = valor.quantize(Decimal("0.01"))
    inteiro, _, centavos = f"{q:.2f}".partition(".")
    sinal = "-" if inteiro.startswith("-") else ""
    inteiro = inteiro.lstrip("-")
    grupos: list[str] = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"


def _layout(titulo: str, corpo_html: str) -> str:
    """Shell HTML mínimo e consistente para os 3 templates."""
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;'
        'margin:0 auto;color:#1a1a1a;line-height:1.5">'
        f'<h1 style="font-size:20px;color:{_COR_VERDE};margin:0 0 16px">'
        f"{escape(titulo)}</h1>"
        f"{corpo_html}"
        '<hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0">'
        f'<p style="font-size:12px;color:#888">{_ASSINATURA} · '
        "Este é um e-mail automático, não responda.</p>"
        "</div>"
    )


def renderizar_onboarding(*, nome: str, link_painel: str) -> EmailMessage:
    """Boas-vindas após o cadastro."""
    nome_e = escape(nome)
    link_e = escape(link_painel)
    corpo = (
        f"<p>Olá, {nome_e}! Sua conta no Arkan está pronta.</p>"
        "<p>A partir de agora você acompanha o que acontece no seu fiscal "
        "sem precisar ser contador — guias, prazos e alertas em um só lugar.</p>"
        f'<p><a href="{link_e}" style="background:{_COR_VERDE};color:#fff;'
        'padding:10px 18px;border-radius:6px;text-decoration:none;'
        'display:inline-block">Abrir meu painel</a></p>'
    )
    texto = (
        f"Olá, {nome}! Sua conta no Arkan está pronta.\n\n"
        "Acompanhe seu fiscal — guias, prazos e alertas em um só lugar.\n"
        f"Abra seu painel: {link_painel}\n\n"
        f"{_ASSINATURA}"
    )
    return EmailMessage(
        to="",  # caller preenche
        assunto=f"Bem-vindo ao Arkan, {nome}",
        html=_layout("Bem-vindo ao Arkan", corpo),
        texto=texto,
        tags=(TipoEmail.ONBOARDING.value,),
    )


def renderizar_fatura(
    *,
    nome: str,
    plano: str,
    valor: Decimal,
    vencimento: date,
    link_pagamento: str,
) -> EmailMessage:
    """Cobrança/fatura da assinatura."""
    nome_e = escape(nome)
    plano_e = escape(plano)
    link_e = escape(link_pagamento)
    venc = vencimento.strftime("%d/%m/%Y")
    valor_fmt = _brl(valor)
    corpo = (
        f"<p>Olá, {nome_e}. Sua fatura do plano <strong>{plano_e}</strong> "
        "está disponível.</p>"
        '<table style="font-size:15px;margin:8px 0">'
        f'<tr><td style="padding:2px 12px 2px 0;color:#666">Valor</td>'
        f'<td><strong>{escape(valor_fmt)}</strong></td></tr>'
        f'<tr><td style="padding:2px 12px 2px 0;color:#666">Vencimento</td>'
        f"<td>{venc}</td></tr></table>"
        f'<p><a href="{link_e}" style="background:{_COR_VERDE};color:#fff;'
        'padding:10px 18px;border-radius:6px;text-decoration:none;'
        'display:inline-block">Pagar agora</a></p>'
    )
    texto = (
        f"Olá, {nome}. Sua fatura do plano {plano} está disponível.\n\n"
        f"Valor: {valor_fmt}\n"
        f"Vencimento: {venc}\n"
        f"Pague em: {link_pagamento}\n\n"
        f"{_ASSINATURA}"
    )
    return EmailMessage(
        to="",
        assunto=f"Sua fatura Arkan — {plano}",
        html=_layout("Sua fatura está pronta", corpo),
        texto=texto,
        tags=(TipoEmail.FATURA.value,),
    )


def renderizar_alerta_fiscal(
    *,
    nome: str,
    titulo: str,
    mensagem: str,
    link_painel: str,
    prazo: date | None = None,
) -> EmailMessage:
    """Alerta fiscal — ``titulo``/``mensagem`` JÁ traduzidos (sem jargão cru)."""
    nome_e = escape(nome)
    msg_e = escape(mensagem)
    link_e = escape(link_painel)
    prazo_html = (
        f'<p style="font-size:15px"><strong>Prazo:</strong> '
        f"{prazo.strftime('%d/%m/%Y')}</p>"
        if prazo
        else ""
    )
    corpo = (
        f"<p>Olá, {nome_e}.</p>"
        f"<p>{msg_e}</p>"
        f"{prazo_html}"
        f'<p><a href="{link_e}" style="background:{_COR_VERDE};color:#fff;'
        'padding:10px 18px;border-radius:6px;text-decoration:none;'
        'display:inline-block">Ver no painel</a></p>'
    )
    prazo_txt = f"Prazo: {prazo.strftime('%d/%m/%Y')}\n" if prazo else ""
    texto = (
        f"Olá, {nome}.\n\n"
        f"{mensagem}\n"
        f"{prazo_txt}"
        f"Veja no painel: {link_painel}\n\n"
        f"{_ASSINATURA}"
    )
    return EmailMessage(
        to="",
        assunto=f"Arkan: {titulo}",
        html=_layout(titulo, corpo),
        texto=texto,
        tags=(TipoEmail.ALERTA_FISCAL.value,),
    )
