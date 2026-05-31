"""Integração assistente ↔ marketplace — parceiros sugeridos (Sprint 13 PR2)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.assistente.schemas import PerguntaIn
from app.modules.assistente.service import responder_pergunta


def _settings() -> MagicMock:
    s = MagicMock()
    s.OLLAMA_URL = "http://localhost:11434"
    return s


def _empresa(uf: str | None = "SP") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        razao_social="Loja Teste",
        nome_fantasia=None,
        cnpj="12345678000195",
        regime_tributario="simples_nacional",
        perfil_ui="sn_sem_funcionarios",
        anexo_simples="I",
        cnae_principal="4711301",
        municipio="São Paulo",
        uf=uf,
        faturamento_12m=None,
    )


def _parceiro(
    *, nome: str, especialidades: list[str], rating: Decimal | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        nome=nome,
        crc_numero="123",
        crc_uf="SP",
        crc_status="ativo",
        especialidades=list(especialidades),
        uf_atuacao=None,
        rating_medio=rating,
        total_consultas=0,
        taxa_resposta_horas=None,
        sla_resposta_horas=24,
        oab_numero=None,
        ativo=True,
    )


@pytest.mark.asyncio
async def test_out_of_scope_com_parceiros_devolve_top_3() -> None:
    empresa_id = uuid.uuid4()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    parceiros = [
        _parceiro(nome=f"Adv {i}", especialidades=["contencioso"], rating=Decimal(str(5 - i * 0.5)))
        for i in range(5)
    ]
    parceiro_repo = AsyncMock()
    parceiro_repo.listar_ativos = AsyncMock(return_value=parceiros)

    session = AsyncMock()
    llm_client = AsyncMock()

    with (
        patch(
            "app.modules.assistente.service.EmpresaRepo", return_value=empresa_repo
        ),
        patch(
            "app.modules.assistente.service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
    ):
        resposta = await responder_pergunta(
            empresa_id,
            PerguntaIn(pergunta="Como me defendo de um auto de infração CARF?"),
            session,
            llm_client,
            _settings(),
        )

    assert resposta.encaminhar_marketplace is True
    assert resposta.categoria_marketplace == "contencioso_fiscal"
    # mapping contencioso_fiscal → analise_intimacao_complexa (categoria_do_assistente)
    assert resposta.categoria_marketplace_sugerida == "analise_intimacao_complexa"
    assert len(resposta.parceiros_sugeridos) == 3
    # Top deve ser o de maior rating
    assert resposta.parceiros_sugeridos[0].nome == "Adv 0"
    llm_client.chamar.assert_not_called()


@pytest.mark.asyncio
async def test_out_of_scope_sem_parceiros_devolve_lista_vazia() -> None:
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    parceiro_repo = AsyncMock()
    parceiro_repo.listar_ativos = AsyncMock(return_value=[])

    session = AsyncMock()
    llm_client = AsyncMock()

    with (
        patch(
            "app.modules.assistente.service.EmpresaRepo", return_value=empresa_repo
        ),
        patch(
            "app.modules.assistente.service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
    ):
        resposta = await responder_pergunta(
            uuid.uuid4(),
            PerguntaIn(pergunta="Quero abrir uma holding familiar"),
            session,
            llm_client,
            _settings(),
        )

    assert resposta.encaminhar_marketplace is True
    assert resposta.categoria_marketplace == "societario"
    assert resposta.categoria_marketplace_sugerida == "holding"
    assert resposta.parceiros_sugeridos == []


@pytest.mark.asyncio
async def test_lookup_parceiros_falha_nao_quebra_resposta() -> None:
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(side_effect=Exception("DB down"))

    session = AsyncMock()
    llm_client = AsyncMock()

    with patch(
        "app.modules.assistente.service.EmpresaRepo", return_value=empresa_repo
    ):
        resposta = await responder_pergunta(
            uuid.uuid4(),
            PerguntaIn(pergunta="Como me defendo de um auto de infração CARF?"),
            session,
            llm_client,
            _settings(),
        )

    # Assistente ainda responde — fallback silencioso.
    assert resposta.encaminhar_marketplace is True
    assert resposta.parceiros_sugeridos == []
