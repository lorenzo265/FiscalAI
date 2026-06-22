"""Testes do ECacService — sincronização + classificação (Sprint 6 PR2)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.e_cac.service import (
    ECacService,
    _extrair_lista_mensagens,
    _parse_data,
)
from app.shared.exceptions import EmpresaNaoEncontrada, SerproErro


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


# ── helpers puros ────────────────────────────────────────────────────────────


class TestExtrairLista:
    def test_dados_dict_mensagens(self) -> None:
        resp = {"dados": {"mensagens": [{"idMensagem": "1"}, {"idMensagem": "2"}]}}
        assert len(_extrair_lista_mensagens(resp)) == 2

    def test_dados_string_json(self) -> None:
        resp = {"dados": '{"mensagens": [{"idMensagem": "1"}]}'}
        assert len(_extrair_lista_mensagens(resp)) == 1

    def test_dados_ausente_retorna_vazio(self) -> None:
        assert _extrair_lista_mensagens({}) == []

    def test_filtra_nao_dict(self) -> None:
        resp = {"dados": {"mensagens": ["bla", {"idMensagem": "1"}, None]}}
        out = _extrair_lista_mensagens(resp)
        assert len(out) == 1


class TestParseData:
    def test_iso8601(self) -> None:
        d = _parse_data("2026-05-16T10:30:00")
        assert d is not None and d.year == 2026

    def test_formato_br(self) -> None:
        d = _parse_data("16/05/2026 10:30")
        assert d is not None and d.month == 5

    def test_string_invalida(self) -> None:
        assert _parse_data("não é data") is None

    def test_nao_string(self) -> None:
        assert _parse_data(12345) is None


# ── service.sincronizar ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.e_cac.service.EmpresaRepo", return_value=empresa_repo), pytest.raises(EmpresaNaoEncontrada):
        await ECacService().sincronizar(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            serpro_client=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_sync_serpro_ausente_retorna_aviso() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())
    with patch("app.modules.e_cac.service.EmpresaRepo", return_value=empresa_repo):
        out = await ECacService().sincronizar(
            session, uuid.uuid4(), uuid.uuid4(), serpro_client=None
        )
    assert out.novas == 0
    assert "não inicializado" in (out.aviso or "")


@pytest.mark.asyncio
async def test_sync_falha_serpro_grava_aviso() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    serpro = AsyncMock()
    serpro.listar_caixa_postal_e_cac = AsyncMock(side_effect=SerproErro("503 down"))

    with patch("app.modules.e_cac.service.EmpresaRepo", return_value=empresa_repo):
        out = await ECacService().sincronizar(
            session, uuid.uuid4(), uuid.uuid4(), serpro_client=serpro
        )

    assert out.novas == 0
    assert out.aviso is not None and "SERPRO" in out.aviso


@pytest.mark.asyncio
async def test_sync_persiste_novas_e_classifica() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    serpro = AsyncMock()
    serpro.listar_caixa_postal_e_cac = AsyncMock(
        return_value={
            "dados": {
                "mensagens": [
                    {
                        "idMensagem": "M001",
                        "assunto": "Intimação Fiscal MPF",
                        "corpo": "Compareça em 30 dias.",
                        "dataEnvio": "2026-05-10T09:00:00",
                    },
                    {
                        "idMensagem": "M002",
                        "assunto": "Atualização cadastral",
                        "corpo": "Sua empresa está ATIVA.",
                        "dataEnvio": "2026-05-12T11:00:00",
                    },
                ]
            }
        }
    )

    inserted_ids: list[uuid.UUID] = [uuid.uuid4(), uuid.uuid4()]
    mensagens_repo = AsyncMock()
    # Duas mensagens inseridas com sucesso.
    mensagens_repo.upsert_recebida = AsyncMock(side_effect=[True, True])
    # Após inserir, listar não classificadas retorna ambas.
    naoclass = [
        SimpleNamespace(
            id=inserted_ids[0],
            assunto="Intimação Fiscal MPF",
            corpo="Compareça em 30 dias.",
        ),
        SimpleNamespace(
            id=inserted_ids[1],
            assunto="Atualização cadastral",
            corpo="Sua empresa está ATIVA.",
        ),
    ]
    mensagens_repo.nao_classificadas = AsyncMock(return_value=naoclass)
    mensagens_repo.aplicar_classificacao = AsyncMock()

    with (
        patch("app.modules.e_cac.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.e_cac.service.MensagensECacRepo",
            return_value=mensagens_repo,
        ),
    ):
        out = await ECacService().sincronizar(
            session, uuid.uuid4(), empresa.id, serpro_client=serpro
        )

    assert out.novas == 2
    assert out.classificadas == 2
    assert out.total_no_lote == 2

    chamadas = mensagens_repo.aplicar_classificacao.await_args_list
    # Primeira mensagem é intimacao com encaminha_marketplace=True
    intimacao_call = chamadas[0]
    assert intimacao_call.kwargs["tipo"] == "intimacao"
    assert intimacao_call.kwargs["prioridade"] == "alta"
    assert intimacao_call.kwargs["encaminhada_marketplace"] is True
    # Segunda é informativa
    informativa_call = chamadas[1]
    assert informativa_call.kwargs["tipo"] == "informativa"
    assert informativa_call.kwargs["encaminhada_marketplace"] is False


@pytest.mark.asyncio
async def test_sync_idempotente_mensagem_repetida() -> None:
    """upsert_recebida retorna False quando a mensagem já existe — contagem ajusta."""
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    serpro = AsyncMock()
    serpro.listar_caixa_postal_e_cac = AsyncMock(
        return_value={
            "dados": {
                "mensagens": [
                    {"idMensagem": "M001", "assunto": "A", "corpo": "x", "dataEnvio": "2026-05-10T09:00:00"},
                ]
            }
        }
    )

    mensagens_repo = AsyncMock()
    mensagens_repo.upsert_recebida = AsyncMock(return_value=False)  # já existia
    mensagens_repo.nao_classificadas = AsyncMock(return_value=[])
    mensagens_repo.aplicar_classificacao = AsyncMock()

    with (
        patch("app.modules.e_cac.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.e_cac.service.MensagensECacRepo",
            return_value=mensagens_repo,
        ),
    ):
        out = await ECacService().sincronizar(
            session, uuid.uuid4(), uuid.uuid4(), serpro_client=serpro
        )

    assert out.novas == 0
    assert out.classificadas == 0
    assert out.total_no_lote == 1
