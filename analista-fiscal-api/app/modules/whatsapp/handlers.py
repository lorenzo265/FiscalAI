"""Handlers de intent para mensagens WhatsApp — lógica pura.

Camada determinística (Camada 1) de classificação de intenção.
Para perguntas complexas, delega ao módulo assistente (Camada 2/3).

Regra UX (§UX do Plano): máximo 3 mensagens por sessão antes de redirecionar
ao dashboard web.
"""

from __future__ import annotations

import re

_PADROES_DAS = [
    r"\bdas\b",
    r"\bsimples nacional\b",
    r"\bquant[ao] (eu )?pag[ao].*?(das|simples|tribut)\b",
    r"\bgui[aã]\b",
    r"\bboleto.{0,20}(das|simples|imposto)\b",
]

_PADROES_AGENDA = [
    r"\bvenciment[ao]\b",
    r"\bcalend[aá]rio\b",
    r"\bprazo\b",
    r"\boblriga[çc][aã]o\b",
    r"\bpagar\b.{0,20}\bquand[ao]\b",
    r"\bquand[ao].{0,20}\bpagar\b",
]

_PADROES_NOTA = [
    r"\bnota\s*fiscal\b",
    r"\bnfs[- ]?e\b",
    r"\bemit[ie]\b",
]

_PADROES_SALDO = [
    r"\bsald[ao]\b",
    r"\bconta\b",
    r"\bbank[oa]\b",
    r"\bextrat[ao]\b",
]

_RESPOSTA_LIMITE_SESSAO = (
    "Você já fez 3 perguntas nesta conversa. Para continuar com mais detalhes, "
    "acesse seu painel completo em: https://app.fiscalai.com.br 📊"
)

_RESPOSTA_FALLBACK = (
    "Não entendi sua pergunta. Posso te ajudar com:\n"
    "• DAS / impostos do Simples Nacional\n"
    "• Calendário fiscal e vencimentos\n"
    "• Emissão de Nota Fiscal\n\n"
    "Tente reformular ou acesse o painel: https://app.fiscalai.com.br"
)

_RESPOSTA_NOTA = (
    "Para emitir notas fiscais, acesse o painel e vá em Notas Fiscais → Emitir NFS-e. "
    "Lá você preenche os dados do serviço e emitimos automaticamente. 📄\n"
    "https://app.fiscalai.com.br/notas"
)

_RESPOSTA_SALDO = (
    "Para ver seu saldo bancário e extrato, acesse Open Finance no painel: "
    "https://app.fiscalai.com.br/financeiro 💰"
)


def _match(texto: str, padroes: list[str]) -> bool:
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in padroes)


def classificar_intent(texto: str) -> str:
    """Classifica a intenção de uma mensagem de texto em PT-BR.

    Returns:
        "das" | "agenda" | "nota" | "saldo" | "assistente" | "desconhecido"
    """
    if not texto or len(texto.strip()) < 2:
        return "desconhecido"

    if _match(texto, _PADROES_DAS):
        return "das"
    if _match(texto, _PADROES_AGENDA):
        return "agenda"
    if _match(texto, _PADROES_NOTA):
        return "nota"
    if _match(texto, _PADROES_SALDO):
        return "saldo"

    return "assistente"


def resposta_para_intent(
    intent: str,
    mensagens_na_sessao: int,
) -> tuple[str, str]:
    """Gera (texto, tipo) de resposta para o intent dado.

    Se a sessão atingiu 3 mensagens, redireciona ao dashboard.
    Retorna (texto_da_resposta, tipo_resposta).
    """
    if mensagens_na_sessao >= 3:
        return _RESPOSTA_LIMITE_SESSAO, "dashboard"

    match intent:
        case "das":
            return (
                "Para ver o valor do seu DAS e emitir a guia, acesse o painel:\n"
                "https://app.fiscalai.com.br/fiscal 💡\n\n"
                "Também posso buscar o valor do mês atual — qual é a competência?",
                "resposta",
            )
        case "agenda":
            return (
                "Seu calendário fiscal está disponível no painel:\n"
                "https://app.fiscalai.com.br/agenda 📅\n\n"
                "Quer que eu liste os próximos vencimentos aqui?",
                "resposta",
            )
        case "nota":
            return _RESPOSTA_NOTA, "resposta"
        case "saldo":
            return _RESPOSTA_SALDO, "resposta"
        case "assistente":
            return (
                "Entendi! Vou buscar essa informação para você. "
                "Por favor aguarde alguns instantes… ⏳",
                "assistente",
            )
        case _:
            return _RESPOSTA_FALLBACK, "fallback"
