"""Testes unitários do NotasService — foco no fluxo de emissão de NFS-e.

Cobre o fix CRIT-2 da auditoria fiscal: o número de RPS deve ser sequencial
por empresa (alocado em EmpresaRepo.alocar_proximo_numero_rps), nunca aleatório.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.notas.schemas import EmitirNfseIn
from app.modules.notas.service import NotasService


def _payload() -> EmitirNfseIn:
    return EmitirNfseIn(
        natureza_operacao=1,
        servico_descricao="Desenvolvimento de sistema fiscal",
        servico_codigo="01.07",
        servico_valor=Decimal("1000.00"),
        aliquota_iss=Decimal("2.00"),
    )


def _empresa_mock(
    empresa_id: uuid.UUID,
    codigo_ibge: str | None = "3550308",
    iss_validada: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=empresa_id,
        cnpj="12345678000195",
        im="123456",
        municipio="São Paulo",
        codigo_municipio_ibge=codigo_ibge,
        aliquota_iss_validada=iss_validada,
    )


@pytest.mark.asyncio
async def test_emitir_nfse_usa_rps_sequencial_zfill_9() -> None:
    """O RPS emitido deve ser o número alocado pelo repo, com zfill(9)."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    focus_client = AsyncMock()
    focus_client.emitir_nfse = AsyncMock(return_value={"status": "processando"})

    empresa_repo_mock = AsyncMock()
    empresa_repo_mock.por_id = AsyncMock(return_value=_empresa_mock(empresa_id))
    empresa_repo_mock.alocar_proximo_numero_rps = AsyncMock(return_value=42)

    notas_repo_mock = AsyncMock()
    notas_repo_mock.criar_nfse = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )

    with (
        patch("app.modules.notas.service.EmpresaRepo", return_value=empresa_repo_mock),
        patch("app.modules.notas.service.NotasRepo", return_value=notas_repo_mock),
    ):
        out = await NotasService().emitir_nfse(
            session, tenant_id, empresa_id, _payload(), focus_client=focus_client
        )

    # numero_rps passado ao Focus deve ser sequencial padded com zeros à esquerda
    chamada_focus = focus_client.emitir_nfse.await_args
    payload_enviado = chamada_focus.args[0]
    assert payload_enviado["numero_rps"] == "000000042"

    # NotasRepo.criar_nfse recebeu o mesmo numero_rps padded
    chamada_repo = notas_repo_mock.criar_nfse.await_args
    assert chamada_repo.kwargs["numero_rps"] == "000000042"

    # alocar_proximo_numero_rps foi chamado com o empresa_id correto
    empresa_repo_mock.alocar_proximo_numero_rps.assert_awaited_once_with(empresa_id)

    assert out.status == "processando"


@pytest.mark.asyncio
async def test_emitir_nfse_rps_diferentes_geram_focus_refs_diferentes() -> None:
    """Duas chamadas com números RPS diferentes devem produzir focus_refs diferentes."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    focus_client = AsyncMock()
    focus_client.emitir_nfse = AsyncMock(return_value={"status": "processando"})

    empresa_repo_mock = AsyncMock()
    empresa_repo_mock.por_id = AsyncMock(return_value=_empresa_mock(empresa_id))
    # Duas alocações consecutivas → 1 e 2
    empresa_repo_mock.alocar_proximo_numero_rps = AsyncMock(side_effect=[1, 2])

    notas_repo_mock = AsyncMock()
    notas_repo_mock.criar_nfse = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )

    with (
        patch("app.modules.notas.service.EmpresaRepo", return_value=empresa_repo_mock),
        patch("app.modules.notas.service.NotasRepo", return_value=notas_repo_mock),
    ):
        out1 = await NotasService().emitir_nfse(
            session, tenant_id, empresa_id, _payload(), focus_client=focus_client
        )
        out2 = await NotasService().emitir_nfse(
            session, tenant_id, empresa_id, _payload(), focus_client=focus_client
        )

    assert out1.focus_ref != out2.focus_ref


@pytest.mark.asyncio
async def test_emitir_nfse_falha_quando_empresa_sem_ibge() -> None:
    """Sem `codigo_municipio_ibge`, emissão levanta MunicipioIbgeAusente (422)."""
    from app.shared.exceptions import MunicipioIbgeAusente

    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    focus_client = AsyncMock()

    empresa_repo_mock = AsyncMock()
    empresa_repo_mock.por_id = AsyncMock(
        return_value=_empresa_mock(empresa_id, codigo_ibge=None)
    )

    with patch("app.modules.notas.service.EmpresaRepo", return_value=empresa_repo_mock):
        with pytest.raises(MunicipioIbgeAusente) as exc_info:
            await NotasService().emitir_nfse(
                session, tenant_id, empresa_id, _payload(), focus_client=focus_client
            )

    assert exc_info.value.http_status == 422
    # Focus não foi chamado — guard preserva idempotência da numeração RPS
    focus_client.emitir_nfse.assert_not_awaited()
    empresa_repo_mock.alocar_proximo_numero_rps.assert_not_awaited()


# ── m5 da auditoria: aviso ISS conforme flag aliquota_iss_validada ───────────


@pytest.mark.asyncio
async def test_emitir_nfse_aviso_iss_aparece_quando_nao_validada() -> None:
    """Empresa sem `aliquota_iss_validada` recebe o `aviso_iss` na resposta."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    focus_client = AsyncMock()
    focus_client.emitir_nfse = AsyncMock(return_value={"status": "processando"})

    empresa_repo_mock = AsyncMock()
    empresa_repo_mock.por_id = AsyncMock(
        return_value=_empresa_mock(empresa_id, iss_validada=False)
    )
    empresa_repo_mock.alocar_proximo_numero_rps = AsyncMock(return_value=1)

    notas_repo_mock = AsyncMock()
    notas_repo_mock.criar_nfse = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )

    with (
        patch("app.modules.notas.service.EmpresaRepo", return_value=empresa_repo_mock),
        patch("app.modules.notas.service.NotasRepo", return_value=notas_repo_mock),
    ):
        out = await NotasService().emitir_nfse(
            session, tenant_id, empresa_id, _payload(), focus_client=focus_client
        )

    assert out.aviso_iss is not None
    assert "LC 116/2003" in out.aviso_iss


@pytest.mark.asyncio
async def test_emitir_nfse_aviso_iss_some_quando_validada() -> None:
    """Empresa com `aliquota_iss_validada=True` não recebe mais o aviso ISS."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    focus_client = AsyncMock()
    focus_client.emitir_nfse = AsyncMock(return_value={"status": "processando"})

    empresa_repo_mock = AsyncMock()
    empresa_repo_mock.por_id = AsyncMock(
        return_value=_empresa_mock(empresa_id, iss_validada=True)
    )
    empresa_repo_mock.alocar_proximo_numero_rps = AsyncMock(return_value=1)

    notas_repo_mock = AsyncMock()
    notas_repo_mock.criar_nfse = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )

    with (
        patch("app.modules.notas.service.EmpresaRepo", return_value=empresa_repo_mock),
        patch("app.modules.notas.service.NotasRepo", return_value=notas_repo_mock),
    ):
        out = await NotasService().emitir_nfse(
            session, tenant_id, empresa_id, _payload(), focus_client=focus_client
        )

    assert out.aviso_iss is None
