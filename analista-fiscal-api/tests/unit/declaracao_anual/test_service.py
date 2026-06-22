"""Testes do DeclaracaoAnualService — guardrails de regime + transmissão."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.declaracao_anual.schemas import (
    DeclaracaoStatus,
    GerarDasnSimeiIn,
    GerarDefisIn,
    SocioDefisIn,
    TipoDeclaracao,
)
from app.modules.declaracao_anual.service import (
    DeclaracaoAnualService,
    _idempotency_key,
)
from app.shared.exceptions import (
    ApuracaoJaExiste,
    EmpresaNaoEncontrada,
    RegimeIncompativel,
    SerproErro,
)


def _empresa(regime: str = "simples_nacional") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        cnpj="12345678000195",
        regime_tributario=regime,
        anexo_simples="III",
    )


def _apuracao_db(empresa_id: uuid.UUID, mes: int, receita: str = "10000") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        competencia=date(2025, mes, 1),
        tipo="das",
        output_jsonb={
            "anexo": "III",
            "anexo_efetivo": "III",
            "receita_mes": receita,
            "valor_das": "650.00",
        },
        transmitido_em=None,
        status="calculado",
    )


# ── helpers puros ────────────────────────────────────────────────────────────


def test_idempotency_key_deterministico() -> None:
    eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert _idempotency_key(eid, "DEFIS", 2025) == _idempotency_key(eid, "DEFIS", 2025)


def test_idempotency_key_anos_diferentes_geram_keys_diferentes() -> None:
    eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert _idempotency_key(eid, "DEFIS", 2025) != _idempotency_key(eid, "DEFIS", 2026)


def test_idempotency_key_tipos_diferentes_geram_keys_diferentes() -> None:
    eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert _idempotency_key(eid, "DEFIS", 2025) != _idempotency_key(eid, "DASN_SIMEI", 2025)


# ── gerar_defis ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gerar_defis_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo
    ), pytest.raises(EmpresaNaoEncontrada):
        await DeclaracaoAnualService().gerar_defis(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            GerarDefisIn(ano_base=2025),
        )


@pytest.mark.asyncio
async def test_gerar_defis_regime_lp_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa(regime="lucro_presumido")
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch(
        "app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo
    ), pytest.raises(RegimeIncompativel):
        await DeclaracaoAnualService().gerar_defis(
            session,
            uuid.uuid4(),
            empresa.id,
            GerarDefisIn(ano_base=2025),
        )


@pytest.mark.asyncio
async def test_gerar_defis_duplicado_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    decl_repo = AsyncMock()
    decl_repo.buscar = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

    with (
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
        pytest.raises(ApuracaoJaExiste),
    ):
        await DeclaracaoAnualService().gerar_defis(
            session,
            uuid.uuid4(),
            empresa.id,
            GerarDefisIn(ano_base=2025),
        )


@pytest.mark.asyncio
async def test_gerar_defis_consolida_e_persiste() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa()
    apuracoes_db = [_apuracao_db(empresa.id, m, "10000") for m in range(1, 13)]

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    apuracao_repo = AsyncMock()
    apuracao_repo.listar_empresa = AsyncMock(return_value=apuracoes_db)

    decl_id = uuid.uuid4()
    decl_repo = AsyncMock()
    decl_repo.buscar = AsyncMock(return_value=None)
    decl_repo.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=decl_id,
            empresa_id=empresa.id,
            ano_base=2025,
            payload_json={"x": 1},
        )
    )

    with (
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.declaracao_anual.service.ApuracaoFiscalRepo",
            return_value=apuracao_repo,
        ),
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
    ):
        out = await DeclaracaoAnualService().gerar_defis(
            session,
            uuid.uuid4(),
            empresa.id,
            GerarDefisIn(
                ano_base=2025,
                lucro_contabil_anual=Decimal("12000"),
                socios=[
                    SocioDefisIn(
                        cpf="52998224725",
                        nome="Único",
                        percentual_capital=Decimal("100"),
                    )
                ],
            ),
        )

    assert out.tipo == TipoDeclaracao.DEFIS
    assert out.status == DeclaracaoStatus.GERADA
    assert out.receita_bruta_anual == Decimal("120000.00")
    decl_repo.criar.assert_awaited_once()


@pytest.mark.asyncio
async def test_gerar_defis_meses_parciais_emite_aviso() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa()
    apuracoes_db = [_apuracao_db(empresa.id, m) for m in range(6, 13)]  # 7 meses

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.listar_empresa = AsyncMock(return_value=apuracoes_db)
    decl_repo = AsyncMock()
    decl_repo.buscar = AsyncMock(return_value=None)
    decl_repo.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(), empresa_id=empresa.id, ano_base=2025, payload_json={}
        )
    )

    with (
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.declaracao_anual.service.ApuracaoFiscalRepo",
            return_value=apuracao_repo,
        ),
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
    ):
        out = await DeclaracaoAnualService().gerar_defis(
            session, uuid.uuid4(), empresa.id, GerarDefisIn(ano_base=2025)
        )

    assert out.aviso is not None and "7 mês" in out.aviso


# ── gerar_dasn_simei ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gerar_dasn_simei_regime_sn_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa(regime="simples_nacional")
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch(
        "app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo
    ), pytest.raises(RegimeIncompativel):
        await DeclaracaoAnualService().gerar_dasn_simei(
            session,
            uuid.uuid4(),
            empresa.id,
            GerarDasnSimeiIn(ano_base=2025),
        )


@pytest.mark.asyncio
async def test_gerar_dasn_excedeu_limite_emite_aviso() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa(regime="mei")
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    decl_repo = AsyncMock()
    decl_repo.buscar = AsyncMock(return_value=None)
    decl_repo.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(), empresa_id=empresa.id, ano_base=2025, payload_json={}
        )
    )
    with (
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
    ):
        out = await DeclaracaoAnualService().gerar_dasn_simei(
            session,
            uuid.uuid4(),
            empresa.id,
            GerarDasnSimeiIn(
                ano_base=2025,
                receita_comercio_industria=Decimal("85000"),
            ),
        )

    assert out.aviso is not None and "desenquadrada" in out.aviso


# ── transmitir ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_defis_sucesso() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa()
    decl_id = uuid.uuid4()
    decl = SimpleNamespace(
        id=decl_id,
        empresa_id=empresa.id,
        tipo="DEFIS",
        ano_base=2025,
        status="gerada",
        idempotency_key="key-1",
        payload_json={"anoCalendario": 2025},
        protocolo=None,
    )

    decl_repo = AsyncMock()
    decl_repo.por_id = AsyncMock(return_value=decl)
    decl_repo.marcar_transmitida = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    serpro = AsyncMock()
    serpro.transmitir_defis = AsyncMock(
        return_value={"dados": {"numeroDeclaracao": "DEFIS-001"}}
    )

    with (
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
    ):
        out = await DeclaracaoAnualService().transmitir(
            session, empresa.id, decl_id, serpro_client=serpro
        )

    assert out.status == DeclaracaoStatus.TRANSMITIDA
    assert out.protocolo == "DEFIS-001"
    decl_repo.marcar_transmitida.assert_awaited_once()
    serpro.transmitir_defis.assert_awaited_once()


@pytest.mark.asyncio
async def test_transmitir_dasn_chama_endpoint_correto() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa(regime="mei")
    decl_id = uuid.uuid4()
    decl = SimpleNamespace(
        id=decl_id,
        empresa_id=empresa.id,
        tipo="DASN_SIMEI",
        ano_base=2025,
        status="gerada",
        idempotency_key="key-2",
        payload_json={"anoCalendario": 2025},
        protocolo=None,
    )

    decl_repo = AsyncMock()
    decl_repo.por_id = AsyncMock(return_value=decl)
    decl_repo.marcar_transmitida = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    serpro = AsyncMock()
    serpro.transmitir_dasn_simei = AsyncMock(
        return_value={"dados": {"numeroDeclaracao": "DASN-001"}}
    )
    serpro.transmitir_defis = AsyncMock()

    with (
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
    ):
        out = await DeclaracaoAnualService().transmitir(
            session, empresa.id, decl_id, serpro_client=serpro
        )

    assert out.protocolo == "DASN-001"
    serpro.transmitir_dasn_simei.assert_awaited_once()
    serpro.transmitir_defis.assert_not_awaited()


@pytest.mark.asyncio
async def test_transmitir_ja_transmitida_idempotente() -> None:
    session = AsyncMock()
    empresa = _empresa()
    decl_id = uuid.uuid4()
    decl = SimpleNamespace(
        id=decl_id,
        empresa_id=empresa.id,
        tipo="DEFIS",
        ano_base=2025,
        status="transmitida",
        protocolo="ALREADY",
        idempotency_key="k",
        payload_json={},
    )

    decl_repo = AsyncMock()
    decl_repo.por_id = AsyncMock(return_value=decl)

    with patch(
        "app.modules.declaracao_anual.service.DeclaracaoAnualRepo", return_value=decl_repo
    ):
        out = await DeclaracaoAnualService().transmitir(
            session, empresa.id, decl_id, serpro_client=AsyncMock()
        )

    assert out.status == DeclaracaoStatus.TRANSMITIDA
    assert out.protocolo == "ALREADY"
    assert "idempotente" in out.mensagem.lower()


@pytest.mark.asyncio
async def test_transmitir_serpro_erro_marca_erro() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa()
    decl_id = uuid.uuid4()
    decl = SimpleNamespace(
        id=decl_id,
        empresa_id=empresa.id,
        tipo="DEFIS",
        ano_base=2025,
        status="gerada",
        idempotency_key="k",
        payload_json={},
        protocolo=None,
    )

    decl_repo = AsyncMock()
    decl_repo.por_id = AsyncMock(return_value=decl)
    decl_repo.marcar_erro = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    serpro = AsyncMock()
    serpro.transmitir_defis = AsyncMock(side_effect=SerproErro("422"))

    with (
        patch(
            "app.modules.declaracao_anual.service.DeclaracaoAnualRepo",
            return_value=decl_repo,
        ),
        patch("app.modules.declaracao_anual.service.EmpresaRepo", return_value=empresa_repo),
    ):
        out = await DeclaracaoAnualService().transmitir(
            session, empresa.id, decl_id, serpro_client=serpro
        )

    assert out.status == DeclaracaoStatus.ERRO
    assert out.erro == "SerproErro"
    decl_repo.marcar_erro.assert_awaited_once()
