"""Testes unitários — handlers de intent WhatsApp."""

from __future__ import annotations

import pytest

from app.modules.whatsapp.handlers import classificar_intent, resposta_para_intent


class TestClassificarIntent:
    @pytest.mark.parametrize(
        "texto,intent_esperado",
        [
            ("quanto eu pago de DAS esse mês?", "das"),
            ("preciso pagar meu simples nacional", "das"),
            ("gerar guia DAS de maio", "das"),
            ("qual o vencimento do próximo imposto?", "agenda"),
            ("quando devo pagar FGTS?", "agenda"),
            ("calendário fiscal de julho", "agenda"),
            ("emitir nota fiscal", "nota"),
            ("como emito NFS-e?", "nota"),
            ("qual meu saldo?", "saldo"),
            ("quero ver o extrato do banco", "saldo"),
            ("o que é CSLL?", "assistente"),
            ("me explica o Fator R", "assistente"),
            ("", "desconhecido"),
            (" ", "desconhecido"),
        ],
    )
    def test_classificar(self, texto: str, intent_esperado: str) -> None:
        assert classificar_intent(texto) == intent_esperado


class TestRespostaParaIntent:
    def test_resposta_das(self) -> None:
        texto, tipo = resposta_para_intent("das", 0)
        assert "DAS" in texto or "painel" in texto
        assert tipo == "resposta"

    def test_resposta_agenda(self) -> None:
        texto, tipo = resposta_para_intent("agenda", 0)
        assert tipo == "resposta"

    def test_resposta_nota(self) -> None:
        texto, tipo = resposta_para_intent("nota", 1)
        assert "nota" in texto.lower() or "NFS-e" in texto
        assert tipo == "resposta"

    def test_resposta_saldo(self) -> None:
        texto, tipo = resposta_para_intent("saldo", 0)
        assert tipo == "resposta"

    def test_resposta_assistente_redireciona_painel(self) -> None:
        """m3 da auditoria Sprints 4-6: intent assistente redireciona ao painel
        em vez de prometer resposta que nunca chega."""
        texto, tipo = resposta_para_intent("assistente", 0)
        assert tipo == "dashboard"
        assert "painel" in texto.lower() or "app.fiscalai" in texto

    def test_resposta_desconhecido(self) -> None:
        texto, tipo = resposta_para_intent("desconhecido", 0)
        assert tipo == "fallback"

    def test_limite_sessao_3_mensagens(self) -> None:
        texto, tipo = resposta_para_intent("das", 3)
        assert tipo == "dashboard"
        assert "painel" in texto.lower() or "app.fiscalai" in texto

    def test_limite_sessao_acima_de_3(self) -> None:
        texto, tipo = resposta_para_intent("agenda", 10)
        assert tipo == "dashboard"
