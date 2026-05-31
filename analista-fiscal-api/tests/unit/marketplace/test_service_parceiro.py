"""Testes do ContadorParceiroService — cadastro + curadoria (Sprint 13 PR1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.marketplace.schemas import (
    AprovarParceiroIn,
    CadastrarParceiroIn,
)
from app.modules.marketplace.service import ContadorParceiroService
from app.shared.exceptions import (
    ContadorParceiroNaoEncontrado,
    CrcJaCadastrado,
    EmailParceiroJaCadastrado,
    EspecialidadeInvalida,
)


def _payload_basico(**over: object) -> CadastrarParceiroIn:
    base: dict[str, object] = {
        "nome": "Joana Contadora",
        "email": "joana@example.com",
        "telefone": "11999990001",
        "crc_numero": "123456",
        "crc_uf": "SP",
        "especialidades": ["tributario", "contencioso"],
    }
    base.update(over)
    return CadastrarParceiroIn(**base)  # type: ignore[arg-type]


def _parceiro_db(*, ativo: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        nome="Joana Contadora",
        email="joana@example.com",
        telefone="11999990001",
        cpf=None,
        cnpj=None,
        crc_numero="123456",
        crc_uf="SP",
        crc_status="ativo",
        crc_status_atualizado_em=None,
        especialidades=["tributario", "contencioso"],
        uf_atuacao=None,
        rating_medio=None,
        total_consultas=0,
        taxa_resposta_horas=None,
        sla_resposta_horas=24,
        oab_numero=None,
        oab_uf=None,
        senha_hash=None,
        aceitou_nda_lgpd_em=None,
        ativo=ativo,
        created_at=datetime(2026, 5, 21, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_cadastrar_sucesso_inicia_inativo() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=None)
    repo.por_crc = AsyncMock(return_value=None)
    parceiro = _parceiro_db(ativo=False)
    repo.criar = AsyncMock(return_value=parceiro)

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        out = await ContadorParceiroService().cadastrar(session, _payload_basico())

    assert out.ativo is False
    repo.criar.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cadastrar_email_duplicado_levanta() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=_parceiro_db())

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        with pytest.raises(EmailParceiroJaCadastrado):
            await ContadorParceiroService().cadastrar(session, _payload_basico())


@pytest.mark.asyncio
async def test_cadastrar_crc_duplicado_levanta() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=None)
    repo.por_crc = AsyncMock(return_value=_parceiro_db())

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        with pytest.raises(CrcJaCadastrado):
            await ContadorParceiroService().cadastrar(session, _payload_basico())


@pytest.mark.asyncio
async def test_cadastrar_especialidade_invalida_levanta() -> None:
    session = AsyncMock()
    with patch("app.modules.marketplace.service.ContadorParceiroRepo"):
        with pytest.raises(EspecialidadeInvalida):
            await ContadorParceiroService().cadastrar(
                session,
                _payload_basico(especialidades=["tributario", "futebol"]),
            )


@pytest.mark.asyncio
async def test_aprovar_flipa_ativo_e_registra_nda() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    parceiro = _parceiro_db(ativo=False)
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=parceiro)

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        out = await ContadorParceiroService().aprovar(
            session,
            parceiro.id,
            AprovarParceiroIn(registrar_aceite_nda_lgpd=True),
        )

    assert out.ativo is True
    assert out.aceitou_nda_lgpd_em is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_aprovar_sem_registrar_nda_mantem_null() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    parceiro = _parceiro_db(ativo=False)
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=parceiro)

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        out = await ContadorParceiroService().aprovar(
            session,
            parceiro.id,
            AprovarParceiroIn(registrar_aceite_nda_lgpd=False),
        )

    assert out.ativo is True
    assert out.aceitou_nda_lgpd_em is None


@pytest.mark.asyncio
async def test_aprovar_idempotente_em_parceiro_ja_ativo() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    parceiro = _parceiro_db(ativo=True)
    parceiro.aceitou_nda_lgpd_em = datetime(2026, 5, 20, 12, 0, 0)
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=parceiro)

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        out = await ContadorParceiroService().aprovar(
            session,
            parceiro.id,
            AprovarParceiroIn(registrar_aceite_nda_lgpd=True),
        )

    assert out.ativo is True
    # Idempotente — não chama commit nem altera timestamp existente
    session.commit.assert_not_called()
    assert out.aceitou_nda_lgpd_em == datetime(2026, 5, 20, 12, 0, 0)


@pytest.mark.asyncio
async def test_aprovar_parceiro_inexistente_levanta() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=None)

    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo", return_value=repo
    ):
        with pytest.raises(ContadorParceiroNaoEncontrado):
            await ContadorParceiroService().aprovar(
                session, uuid.uuid4(), AprovarParceiroIn()
            )
