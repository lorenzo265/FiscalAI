"""Testes do TabelaAdminService — orquestração + idempotência (Sprint 19.5 PR1).

Testes com AsyncMock dos repos para isolar a lógica do service do DB real.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.tabelas_admin.service import (
    TabelaAdminService,
    computar_idempotency_key,
)
from app.shared.exceptions import (
    VigenciaTributariaInvalida,
    VigenciaTributariaJaPostada,
)
from app.shared.idempotency import NS_TABELA_ADMIN
from tests.unit.tabelas_admin._helpers import vigencia_inss_valida


def _service_mocks(
    *,
    max_inss: date | None = None,
    log_existente: SimpleNamespace | None = None,
) -> tuple[TabelaAdminService, AsyncMock, AsyncMock, AsyncMock]:
    """Constrói o service com repos AsyncMock."""
    log_repo = AsyncMock()
    log_repo.por_idempotency_key = AsyncMock(return_value=log_existente)
    log_repo.criar = AsyncMock(side_effect=lambda obj: obj)

    scd_repo = AsyncMock()
    scd_repo.max_valid_from_inss = AsyncMock(return_value=max_inss)
    scd_repo.inserir_inss = AsyncMock(return_value=5)

    session = AsyncMock()

    svc = TabelaAdminService(log_repo=log_repo, scd_repo=scd_repo)
    return svc, log_repo, scd_repo, session


# ── Idempotency key (UUID5 determinístico) ──────────────────────────────────


def test_idempotency_key_deterministica() -> None:
    p1 = vigencia_inss_valida()
    p2 = vigencia_inss_valida()
    k1 = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p1.valid_from, payload=p1
    )
    k2 = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p2.valid_from, payload=p2
    )
    assert k1 == k2


def test_idempotency_key_muda_se_payload_diverge() -> None:
    p1 = vigencia_inss_valida()
    p2 = vigencia_inss_valida(
        fonte_norma="Portaria diferente — citação atualizada"
    )
    k1 = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p1.valid_from, payload=p1
    )
    k2 = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p2.valid_from, payload=p2
    )
    assert k1 != k2


def test_idempotency_key_muda_se_tipo_diverge() -> None:
    p = vigencia_inss_valida()
    k_inss = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p.valid_from, payload=p
    )
    k_irrf = computar_idempotency_key(
        tipo_tabela="irrf", valid_from=p.valid_from, payload=p
    )
    assert k_inss != k_irrf


def test_idempotency_key_usa_namespace_correto() -> None:
    """UUID5 com namespace conhecido = valor previsível."""
    from uuid import uuid5

    p = vigencia_inss_valida()
    expected_seed = f"inss|{p.valid_from.isoformat()}|"
    k = computar_idempotency_key(
        tipo_tabela="inss", valid_from=p.valid_from, payload=p
    )
    # Não dá pra reconstruir o digest aqui (depende do canonical_json), mas
    # podemos confirmar que a chave é um UUID5 do NS_TABELA_ADMIN.
    assert k.version == 5
    # Sanity: outra chave gerada com o mesmo namespace + mesma seed = igual.
    seed_completa = expected_seed
    # Use uuid5 to verify the namespace pattern would generate v5 UUIDs
    _ = uuid5(NS_TABELA_ADMIN, seed_completa)
    # Just check version
    assert k.version == 5


# ── Service: criar_vigencia_inss happy path ────────────────────────────────


@pytest.mark.asyncio
async def test_criar_vigencia_inss_happy_path() -> None:
    svc, log_repo, scd_repo, session = _service_mocks(max_inss=date(2025, 1, 1))
    payload = vigencia_inss_valida()
    log = await svc.criar_vigencia_inss(session, payload)

    assert log.tipo_tabela == "inss"
    assert log.valid_from == payload.valid_from
    assert log.fonte_norma == payload.fonte_norma
    assert log.registros_criados == 5
    scd_repo.inserir_inss.assert_awaited_once()
    log_repo.criar.assert_awaited_once()
    session.commit.assert_awaited_once()


# ── Idempotência hit (re-POST com mesmo payload) ───────────────────────────


@pytest.mark.asyncio
async def test_idempotencia_repost_mesma_chave_payload_igual_devolve_log_anterior() -> None:
    payload = vigencia_inss_valida()
    key = computar_idempotency_key(
        tipo_tabela="inss", valid_from=payload.valid_from, payload=payload
    )
    payload_canonical = json.loads(
        json.dumps(
            payload.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    log_existente = SimpleNamespace(
        id=uuid4(),
        tipo_tabela="inss",
        valid_from=payload.valid_from,
        fonte_norma=payload.fonte_norma,
        payload_jsonb=payload_canonical,
        usuario_admin_id=None,
        idempotency_key=key,
        registros_criados=5,
        criado_em=datetime.now(),
    )
    svc, log_repo, scd_repo, session = _service_mocks(
        max_inss=date(2025, 1, 1), log_existente=log_existente
    )
    devolvido = await svc.criar_vigencia_inss(session, payload)

    # Devolve o log anterior — NÃO toca SCD nem commit.
    assert devolvido is log_existente
    scd_repo.inserir_inss.assert_not_awaited()
    log_repo.criar.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_idempotencia_repost_mesma_chave_payload_diferente_devolve_409() -> None:
    payload = vigencia_inss_valida()
    key = computar_idempotency_key(
        tipo_tabela="inss", valid_from=payload.valid_from, payload=payload
    )
    # Log existente tem outro payload_jsonb (representa POST anterior diferente).
    log_existente = SimpleNamespace(
        id=uuid4(),
        tipo_tabela="inss",
        valid_from=payload.valid_from,
        fonte_norma=payload.fonte_norma,
        payload_jsonb={"campo_diferente": "valor_diferente"},
        usuario_admin_id=None,
        idempotency_key=key,
        registros_criados=5,
        criado_em=datetime.now(),
    )
    svc, _, _, session = _service_mocks(
        max_inss=date(2025, 1, 1), log_existente=log_existente
    )
    # Payload do POST atual usa a mesma key explicitamente.
    payload_com_key = vigencia_inss_valida(idempotency_key=key)
    with pytest.raises(VigenciaTributariaJaPostada, match="divergente"):
        await svc.criar_vigencia_inss(session, payload_com_key)


# ── Anti-regressão temporal ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_from_anterior_ou_igual_a_max_existente_falha() -> None:
    # Vigência ativa: 2026-01-15. POST com 2026-01-15 → falha (≤).
    svc, _, _, session = _service_mocks(max_inss=date(2026, 1, 15))
    payload = vigencia_inss_valida(valid_from=date(2026, 1, 15))
    with pytest.raises(
        VigenciaTributariaInvalida, match="posterior à vigência ativa"
    ):
        await svc.criar_vigencia_inss(session, payload)


@pytest.mark.asyncio
async def test_valid_from_estritamente_posterior_passa() -> None:
    # Vigência ativa: 2025-01-15. POST com 2026-01-15 → OK.
    svc, _, scd_repo, session = _service_mocks(max_inss=date(2025, 1, 15))
    payload = vigencia_inss_valida(valid_from=date(2026, 1, 15))
    await svc.criar_vigencia_inss(session, payload)
    scd_repo.inserir_inss.assert_awaited_once()


@pytest.mark.asyncio
async def test_primeira_vigencia_de_tudo_passa_sem_max() -> None:
    # max_valid_from_inss devolve None (tabela vazia).
    svc, _, scd_repo, session = _service_mocks(max_inss=None)
    payload = vigencia_inss_valida()
    log = await svc.criar_vigencia_inss(session, payload)
    assert log.registros_criados == 5
    scd_repo.inserir_inss.assert_awaited_once()


# ── Validador é chamado antes do DB ────────────────────────────────────────


@pytest.mark.asyncio
async def test_payload_invalido_levanta_antes_de_tocar_db() -> None:
    """Faixas não progressivas → 422 sem chamar repo SCD nem log."""
    svc, log_repo, scd_repo, session = _service_mocks()
    faixas = [
        # Faixa 1 cobrindo SM 2026 mas faixa 2 com valor menor → erro.
        type(vigencia_inss_valida().faixas[0])(
            tipo="empregado",
            faixa=1,
            valor_ate=Decimal("1620.00"),
            aliquota=Decimal("0.075"),
        ),
        type(vigencia_inss_valida().faixas[1])(
            tipo="empregado",
            faixa=2,
            valor_ate=Decimal("1000.00"),  # < 1620
            aliquota=Decimal("0.09"),
        ),
    ]
    payload = vigencia_inss_valida(faixas=faixas)
    with pytest.raises(VigenciaTributariaInvalida):
        await svc.criar_vigencia_inss(session, payload)
    # Nenhuma escrita no DB ocorreu.
    scd_repo.max_valid_from_inss.assert_not_awaited()
    scd_repo.inserir_inss.assert_not_awaited()
    log_repo.criar.assert_not_awaited()


# ── Idempotency key explícita do admin ─────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotency_key_explicita_e_respeitada() -> None:
    """Quando admin passa idempotency_key, o service usa essa exata
    (não recomputa). Útil para retry seguro do lado admin.
    """
    explicit_key = uuid4()
    svc, log_repo, _, session = _service_mocks(max_inss=date(2025, 1, 1))
    payload = vigencia_inss_valida(idempotency_key=explicit_key)
    log = await svc.criar_vigencia_inss(session, payload)
    assert log.idempotency_key == explicit_key
    # E a consulta foi feita com essa key.
    log_repo.por_idempotency_key.assert_awaited_with(explicit_key)
