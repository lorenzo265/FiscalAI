"""Testes do AlertaAdminService — varredura + ops + hooks (Sprint 19.5 PR2)."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.modules.tabelas_admin.alertas_repo import _build_idempotency_key
from app.modules.tabelas_admin.alertas_service import AlertaAdminService

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _svc(
    *,
    inss: date | None = None,
    irrf: date | None = None,
    fgts: date | None = None,
    simples: date | None = None,
    presuncao: date | None = None,
    icms_por_uf: dict[str, date] | None = None,
    cbs_ativa: date | None = None,
    cbs_futura: date | None = None,
    upsert_devolve: list[object] | None = None,
) -> tuple[AlertaAdminService, AsyncMock, AsyncMock, AsyncMock]:
    """Constrói o service com `alerta_repo` e `scd_repo` mockados."""
    scd_repo = AsyncMock()
    scd_repo.valid_from_ativa_inss = AsyncMock(return_value=inss)
    scd_repo.valid_from_ativa_irrf = AsyncMock(return_value=irrf)
    scd_repo.valid_from_ativa_fgts = AsyncMock(return_value=fgts)
    scd_repo.valid_from_ativa_simples = AsyncMock(return_value=simples)
    scd_repo.valid_from_ativa_presuncao = AsyncMock(return_value=presuncao)
    scd_repo.valid_from_ativa_icms_por_uf = AsyncMock(
        return_value=icms_por_uf or {}
    )
    scd_repo.valid_from_ativa_cbs_ibs = AsyncMock(return_value=cbs_ativa)
    scd_repo.proxima_vigencia_futura_cbs_ibs = AsyncMock(
        return_value=cbs_futura
    )

    alerta_repo = AsyncMock()
    if upsert_devolve is not None:
        # Sequência: cada chamada devolve item da lista (None = já existia).
        alerta_repo.upsert_idempotente = AsyncMock(
            side_effect=list(upsert_devolve)
        )
    else:
        alerta_repo.upsert_idempotente = AsyncMock(
            return_value=SimpleNamespace(id=uuid4())
        )

    session = AsyncMock()
    svc = AlertaAdminService(alerta_repo=alerta_repo, scd_repo=scd_repo)
    return svc, alerta_repo, scd_repo, session


# ── Idempotency key (UUID5 estável) ────────────────────────────────────────


def test_idempotency_key_alerta_deterministica_por_tipo_tabela_ano() -> None:
    k1 = _build_idempotency_key(
        tipo="tabela_tributaria_vencida", tipo_tabela="inss", ano=2026
    )
    k2 = _build_idempotency_key(
        tipo="tabela_tributaria_vencida", tipo_tabela="inss", ano=2026
    )
    assert k1 == k2
    assert k1.version == 5


def test_idempotency_key_alerta_muda_por_ano() -> None:
    k_26 = _build_idempotency_key(
        tipo="tabela_tributaria_vencida", tipo_tabela="inss", ano=2026
    )
    k_27 = _build_idempotency_key(
        tipo="tabela_tributaria_vencida", tipo_tabela="inss", ano=2027
    )
    assert k_26 != k_27


# ── Varredura ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_varredura_marco_2026_com_vigencias_2025_cria_alertas() -> None:
    svc, alerta_repo, _, session = _svc(
        inss=date(2025, 1, 1),
        irrf=date(2025, 1, 1),
        fgts=date(2025, 1, 1),
        simples=date(2024, 1, 1),
        presuncao=date(2020, 1, 1),
        # ICMS UFs ativas com vigência 2023 (>2 anos)
        icms_por_uf={"SP": date(2023, 1, 1)},
        cbs_ativa=date(2026, 1, 1),
        cbs_futura=None,
    )
    criados, ja_existiam = await svc.verificar_e_alertar(
        session, hoje=date(2026, 3, 15)
    )
    # INSS critico + IRRF critico + ICMS SP aviso = 3 alertas.
    # FGTS 2025 (1 ano) → não alerta.
    # SN 2024 (2 anos) → não alerta.
    # Presunção 2020 (6 anos) → não alerta (limite 10 anos).
    # CBS recente → não alerta.
    assert criados == 3
    assert ja_existiam == 0
    assert alerta_repo.upsert_idempotente.await_count == 3
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_varredura_janeiro_2026_com_vigencias_2025_nao_alerta() -> None:
    """Janeiro tolerante — Portaria pode estar saindo."""
    svc, alerta_repo, _, session = _svc(
        inss=date(2025, 1, 1),
        irrf=date(2025, 1, 1),
        fgts=date(2025, 1, 1),
        simples=date(2025, 1, 1),
        presuncao=date(2025, 1, 1),
        icms_por_uf={"SP": date(2025, 1, 1)},
        cbs_ativa=date(2026, 1, 1),
    )
    criados, ja_existiam = await svc.verificar_e_alertar(
        session, hoje=date(2026, 1, 10)
    )
    assert criados == 0
    assert alerta_repo.upsert_idempotente.await_count == 0


@pytest.mark.asyncio
async def test_varredura_segundo_run_no_mesmo_periodo_e_idempotente() -> None:
    """Worker rodando 2× no mesmo dia: upsert devolve None na 2ª = "já existia"."""
    svc, alerta_repo, _, session = _svc(
        inss=date(2025, 1, 1),
        irrf=date(2025, 1, 1),
        # ICMS SP vigência 2023 também ativará — total: INSS+IRRF+ICMS_SP=3.
        icms_por_uf={"SP": date(2023, 1, 1)},
        upsert_devolve=[None, None, None],  # 3 tipos triggerm, todos no-op
    )
    criados, ja_existiam = await svc.verificar_e_alertar(
        session, hoje=date(2026, 3, 15)
    )
    assert criados == 0
    assert ja_existiam == 3


@pytest.mark.asyncio
async def test_varredura_continua_mesmo_se_um_tipo_lanca() -> None:
    """Se ``valid_from_ativa_inss`` levanta, o worker continua nos demais tipos.

    Para isolar o efeito, todos os outros tipos têm vigência recente (sem
    alerta) — exceto IRRF (crítico 2025→2026) e ICMS SP (aviso 2023>2anos).
    """
    svc, alerta_repo, scd_repo, session = _svc(
        irrf=date(2025, 1, 1),
        # Vigências recentes nos outros = sem alerta
        fgts=date(2025, 1, 1),
        simples=date(2025, 1, 1),
        presuncao=date(2025, 1, 1),
        icms_por_uf={"SP": date(2023, 1, 1)},
        cbs_ativa=date(2026, 1, 1),
    )
    # Força exception em INSS
    scd_repo.valid_from_ativa_inss = AsyncMock(side_effect=RuntimeError("boom"))
    criados, ja_existiam = await svc.verificar_e_alertar(
        session, hoje=date(2026, 3, 15)
    )
    # INSS pulado, IRRF + ICMS_SP criam alertas
    assert criados == 2


# ── Resolver / snooze ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_alerta_existente() -> None:
    alerta_id = uuid4()
    alerta_resolvido = SimpleNamespace(
        id=alerta_id, resolvido_em=datetime.now(_TZ_BR)
    )
    svc, alerta_repo, _, session = _svc()
    alerta_repo.resolver = AsyncMock(return_value=alerta_resolvido)
    result = await svc.resolver(session, alerta_id)
    assert result is alerta_resolvido
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolver_alerta_inexistente_devolve_none() -> None:
    svc, alerta_repo, _, session = _svc()
    alerta_repo.resolver = AsyncMock(return_value=None)
    result = await svc.resolver(session, uuid4())
    assert result is None
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snooze_alerta_existente() -> None:
    alerta_id = uuid4()
    alerta_em_snooze = SimpleNamespace(id=alerta_id, resolvido_em=datetime.now(_TZ_BR))
    svc, alerta_repo, _, session = _svc()
    alerta_repo.snooze = AsyncMock(return_value=alerta_em_snooze)
    result = await svc.snooze(session, alerta_id, dias=30)
    assert result is alerta_em_snooze
    alerta_repo.snooze.assert_awaited_with(alerta_id, dias=30)


# ── Hook digest admin ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alertas_para_digest_admin_devolve_bullets_markdown() -> None:
    svc, alerta_repo, _, _ = _svc()
    alerta_repo.listar = AsyncMock(
        return_value=[
            SimpleNamespace(
                titulo="Tabela INSS 2026 não atualizada",
                descricao="Portaria de janeiro/2026 já deveria ter sido publicada.",
            ),
            SimpleNamespace(
                titulo="Tabela IRRF 2026 não atualizada",
                descricao="Lei + RFB pendentes.",
            ),
        ]
    )
    bullets = await svc.alertas_para_digest_admin()
    assert len(bullets) == 2
    assert bullets[0].startswith("⚠ *Tabela INSS")
    assert "Portaria" in bullets[0]


@pytest.mark.asyncio
async def test_alertas_para_digest_admin_sem_alertas_devolve_lista_vazia() -> None:
    svc, alerta_repo, _, _ = _svc()
    alerta_repo.listar = AsyncMock(return_value=[])
    bullets = await svc.alertas_para_digest_admin()
    assert bullets == []


# ── Sprint 19.6 PR3 (#42) — digest admin completo ──────────────────────────


@pytest.mark.asyncio
async def test_digest_admin_completo_com_criticos_emite_bullets() -> None:
    """Quando há alertas críticos, emite texto markdown completo com bullets."""
    svc, alerta_repo, _, _ = _svc()
    alerta_repo.listar = AsyncMock(
        side_effect=[
            # 1ª chamada: severidade='critico' → 2 itens
            [
                SimpleNamespace(
                    titulo="Tabela INSS 2026 não atualizada",
                    descricao="Portaria de janeiro/2026 deve ter sido publicada.",
                ),
                SimpleNamespace(
                    titulo="Tabela IRRF 2026 não atualizada",
                    descricao="Lei + RFB pendentes.",
                ),
            ],
            # 2ª chamada: severidade='aviso' → 3 itens
            [SimpleNamespace(), SimpleNamespace(), SimpleNamespace()],
            # 3ª chamada: severidade='info' → 1 item
            [SimpleNamespace()],
        ]
    )
    out = await svc.montar_digest_admin_completo()
    texto = out["texto"]
    assert isinstance(texto, str)
    assert "Digest Admin" in texto
    assert "Alertas críticos (2)" in texto
    assert "Tabela INSS 2026" in texto
    assert "Tabela IRRF 2026" in texto
    assert "aviso: 3" in texto
    assert "info: 1" in texto
    assert out["alertas_count"] == 6
    assert out["alertas_por_severidade"] == {
        "critico": 2,
        "aviso": 3,
        "info": 1,
    }


@pytest.mark.asyncio
async def test_digest_admin_sem_criticos_emite_tudo_em_dia() -> None:
    """Sem alertas críticos, mensagem curta '✅ Tudo em dia'."""
    svc, alerta_repo, _, _ = _svc()
    alerta_repo.listar = AsyncMock(
        side_effect=[
            [],  # crítico: nenhum
            [SimpleNamespace()],  # aviso: 1
            [],  # info: nenhum
        ]
    )
    out = await svc.montar_digest_admin_completo()
    texto = out["texto"]
    assert "Tudo em dia" in texto
    assert "Sem alertas críticos" in texto
    # Total exclusivo de críticos = 1 (apenas aviso)
    assert out["alertas_count"] == 1


@pytest.mark.asyncio
async def test_digest_admin_aceita_base_url_custom() -> None:
    """Operador pode passar URL custom (ex.: staging)."""
    svc, alerta_repo, _, _ = _svc()
    alerta_repo.listar = AsyncMock(return_value=[])
    out = await svc.montar_digest_admin_completo(
        base_url_painel="https://staging.fiscalai.local/admin"
    )
    assert "staging.fiscalai.local" in out["texto"]
