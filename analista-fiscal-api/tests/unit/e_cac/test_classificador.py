"""Testes do classificador determinístico de mensagens e-CAC (Sprint 6 PR2)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.e_cac.classificador import CLASSIFICADOR_VERSAO, classificar


class TestClassificarIntimacao:
    def test_assunto_com_intimacao(self) -> None:
        r = classificar("Intimação Fiscal - MPF 0001/2026", None)
        assert r.tipo == "intimacao"
        assert r.prioridade == "alta"
        assert r.encaminha_marketplace is True
        assert r.versao == CLASSIFICADOR_VERSAO

    def test_intimacao_sem_acento(self) -> None:
        r = classificar("INTIMACAO PARA COMPARECER", None)
        assert r.tipo == "intimacao"
        assert r.prioridade == "alta"

    def test_auto_de_infracao_no_corpo(self) -> None:
        r = classificar("Notificação", "Foi lavrado AUTO DE INFRAÇÃO contra...")
        assert r.tipo == "intimacao"
        assert r.encaminha_marketplace is True

    def test_mpf_em_caixa_baixa(self) -> None:
        r = classificar("Comunicado", "mpf instaurado em 10/04/2026")
        assert r.tipo == "intimacao"


class TestClassificarAviso:
    def test_pendencia(self) -> None:
        r = classificar("Aviso de Pendência", "Há pendências no seu CNPJ.")
        assert r.tipo == "aviso"
        assert r.prioridade == "media"

    def test_divergencia_com_prazo_curto_eleva_prioridade(self) -> None:
        r = classificar(
            "Divergência detectada",
            "Você tem prazo de 15 dias para regularizar.",
        )
        assert r.tipo == "aviso"
        assert r.prioridade == "alta"

    def test_cobranca(self) -> None:
        r = classificar("Cobrança", "Saldo devedor pendente.")
        assert r.tipo == "aviso"


class TestClassificarInformativa:
    def test_assunto_neutro(self) -> None:
        r = classificar(
            "Atualização cadastral disponível",
            "Sua empresa consta como ATIVA na RFB.",
        )
        assert r.tipo == "informativa"
        assert r.prioridade == "baixa"
        assert r.encaminha_marketplace is False


class TestExtracaoPrazo:
    def test_data_limite_explicita_no_corpo(self) -> None:
        r = classificar("Aviso", "Regularizar até 30/06/2026, prazo final.")
        assert r.prazo_resposta == date(2026, 6, 30)

    def test_data_invalida_retorna_none(self) -> None:
        r = classificar("Aviso", "Regularizar até 99/99/2026.")
        assert r.prazo_resposta is None

    def test_sem_prazo(self) -> None:
        r = classificar("Aviso", "Sem prazo determinado.")
        assert r.prazo_resposta is None
