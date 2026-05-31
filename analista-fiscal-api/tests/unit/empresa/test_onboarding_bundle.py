"""Testes do ``OnboardingBundleService`` (Sprint 19 PR4).

Verifica:
  * Guard: empresa não encontrada → ``EmpresaNaoEncontrada``.
  * Guard: lote_importacao concluído → ``OnboardingConflitoComImportacao``.
  * Clone do plano referencial é chamado (delegação ao ContabilService).
  * Checklist é contextualizada por ``perfil_ui``.
  * Checklist marca ``concluido=True`` para passos cujo estado já é "feito".
  * Idempotência — duas chamadas seguidas re-avaliam estado, não regridem.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.contabil.schemas import ClonarPlanoOut
from app.modules.empresa.onboarding_bundle import OnboardingBundleService
from app.modules.empresa.schemas import PerfilUI
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    OnboardingConflitoComImportacao,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _empresa(
    *,
    perfil_ui: str = "sn_sem_funcionarios",
    aliquota_iss_validada: bool = False,
    whatsapp_phone: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        perfil_ui=perfil_ui,
        aliquota_iss_validada=aliquota_iss_validada,
        whatsapp_phone=whatsapp_phone,
    )


def _session_com(
    *,
    empresa: SimpleNamespace | None,
    lotes_concluidos: int = 0,
) -> AsyncMock:
    """Mock AsyncSession que responde:
      * EmpresaRepo.por_id → o ``empresa`` passado (ou None).
      * count(LoteImportacao concluído) → ``lotes_concluidos``.
    """
    # EmpresaRepo.por_id chama session.execute(...).scalar_one_or_none() para
    # o select Empresa; depois o _guard chama session.execute(select count)
    # → scalar_one(). Mock os dois com side_effect ordenado.
    empresa_result = MagicMock()
    empresa_result.scalar_one_or_none = MagicMock(return_value=empresa)

    count_result = MagicMock()
    count_result.scalar_one = MagicMock(return_value=lotes_concluidos)

    chamadas = {"i": 0}

    async def _execute(*_args: Any, **_kwargs: Any) -> Any:
        chamadas["i"] += 1
        if chamadas["i"] == 1:
            return empresa_result
        return count_result

    session = AsyncMock()
    session.execute = _execute
    return session


def _mock_contabil_service(criadas: int = 36, existentes: int = 0) -> MagicMock:
    """ContabilService com ``clonar_plano_referencial`` mockado."""
    svc = MagicMock()
    svc.clonar_plano_referencial = AsyncMock(
        return_value=ClonarPlanoOut(
            contas_criadas=criadas,
            contas_existentes=existentes,
            primeira_competencia=date(2026, 1, 1),
        )
    )
    return svc


# ─────────────────────────────────────────────────────────────────────────────
# Guards
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta() -> None:
    session = _session_com(empresa=None)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    with pytest.raises(EmpresaNaoEncontrada):
        await service.executar(
            session,
            tenant_id=uuid4(),
            empresa_id=uuid4(),
            valid_from=date(2026, 1, 1),
            welcome_digest_optin=False,
        )


@pytest.mark.asyncio
async def test_lote_importacao_concluido_bloqueia_com_409() -> None:
    """Plano deve vir do SPED quando houver importação histórica.

    Não tentar clonar o referencial — risco de corrupção de códigos.
    """
    empresa = _empresa()
    session = _session_com(empresa=empresa, lotes_concluidos=1)
    contabil = _mock_contabil_service()
    service = OnboardingBundleService(contabil_service=contabil)

    with pytest.raises(OnboardingConflitoComImportacao) as exc_info:
        await service.executar(
            session,
            tenant_id=uuid4(),
            empresa_id=empresa.id,
            valid_from=date(2026, 1, 1),
            welcome_digest_optin=False,
        )

    assert exc_info.value.http_status == 409
    # E garantimos que NÃO chamou o clone — o guard rejeitou antes.
    contabil.clonar_plano_referencial.assert_not_called()


@pytest.mark.asyncio
async def test_lote_falhou_nao_bloqueia() -> None:
    """Apenas lotes ``concluido`` bloqueiam — lotes ``falhou`` permitem retry
    do bundle (são contados como 0 no guard).
    """
    empresa = _empresa()
    session = _session_com(empresa=empresa, lotes_concluidos=0)
    contabil = _mock_contabil_service()
    service = OnboardingBundleService(contabil_service=contabil)

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    contabil.clonar_plano_referencial.assert_awaited_once()
    assert out.plano_contas_criadas == 36


# ─────────────────────────────────────────────────────────────────────────────
# Clone do plano
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clone_delega_para_contabil_service() -> None:
    empresa = _empresa()
    session = _session_com(empresa=empresa)
    contabil = _mock_contabil_service(criadas=36, existentes=0)
    service = OnboardingBundleService(contabil_service=contabil)
    tenant_id = uuid4()

    await service.executar(
        session,
        tenant_id=tenant_id,
        empresa_id=empresa.id,
        valid_from=date(2026, 6, 15),
        welcome_digest_optin=False,
    )

    contabil.clonar_plano_referencial.assert_awaited_once_with(
        session, tenant_id, empresa.id, date(2026, 6, 15),
    )


@pytest.mark.asyncio
async def test_segunda_chamada_propaga_contas_existentes() -> None:
    """Idempotência: ``ContabilService`` já é idempotente (Sprint 9 PR1).
    Bundle propaga ``contas_existentes=36`` na 2ª chamada — UI mostra que
    plano já estava completo.
    """
    empresa = _empresa()
    session = _session_com(empresa=empresa)
    contabil = _mock_contabil_service(criadas=0, existentes=36)
    service = OnboardingBundleService(contabil_service=contabil)

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert out.plano_contas_criadas == 0
    assert out.plano_contas_existentes == 36


# ─────────────────────────────────────────────────────────────────────────────
# Checklist por perfil_ui
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_checklist_mei_tem_3_passos() -> None:
    empresa = _empresa(perfil_ui="mei")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert out.perfil_ui == PerfilUI.MEI
    assert len(out.proximos_passos) == 3
    chaves = [p.chave for p in out.proximos_passos]
    assert chaves == ["plano_contas_clonado", "iss_validado", "whatsapp_cadastrado"]


@pytest.mark.asyncio
async def test_checklist_simples_tem_4_passos_inclui_pluggy() -> None:
    empresa = _empresa(perfil_ui="sn_sem_funcionarios")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert len(out.proximos_passos) == 4
    assert "pluggy_conectado" in {p.chave for p in out.proximos_passos}


@pytest.mark.asyncio
async def test_checklist_lucro_presumido_tem_5_passos_inclui_sped() -> None:
    empresa = _empresa(perfil_ui="lucro_presumido")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert len(out.proximos_passos) == 5
    chaves = {p.chave for p in out.proximos_passos}
    assert "sped_anual_habilitado" in chaves
    assert "pluggy_conectado" in chaves


@pytest.mark.asyncio
async def test_checklist_perfil_invalido_cai_em_sn_sem_funcionarios() -> None:
    """Defensivo — perfil novo no DB antes do enum não quebra o bundle."""
    empresa = _empresa(perfil_ui="perfil_que_nao_existe")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    # Fallback para sn_sem_funcionarios — 4 passos.
    assert len(out.proximos_passos) == 4


# ─────────────────────────────────────────────────────────────────────────────
# Estado dos passos (concluido)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plano_contas_clonado_e_sempre_concluido_apos_bundle() -> None:
    """Logo após bundle, o passo `plano_contas_clonado` é sempre True —
    independentemente de ser primeira execução ou re-execução."""
    empresa = _empresa()
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    passo_plano = next(p for p in out.proximos_passos if p.chave == "plano_contas_clonado")
    assert passo_plano.concluido is True


@pytest.mark.asyncio
async def test_iss_validado_reflete_estado_da_empresa() -> None:
    empresa = _empresa(aliquota_iss_validada=True)
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    passo_iss = next(p for p in out.proximos_passos if p.chave == "iss_validado")
    assert passo_iss.concluido is True


@pytest.mark.asyncio
async def test_whatsapp_cadastrado_quando_phone_presente() -> None:
    empresa = _empresa(whatsapp_phone="+5511999999999")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    passo_wpp = next(p for p in out.proximos_passos if p.chave == "whatsapp_cadastrado")
    assert passo_wpp.concluido is True


@pytest.mark.asyncio
async def test_endpoint_do_passo_inclui_empresa_id_no_path() -> None:
    """``{empresa_id}`` no template é substituído pelo ID real — frontend
    pode chamar diretamente o endpoint sugerido sem parsing extra.
    """
    empresa = _empresa()
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    passo_iss = next(p for p in out.proximos_passos if p.chave == "iss_validado")
    assert passo_iss.endpoint is not None
    assert str(empresa.id) in passo_iss.endpoint
    assert "{empresa_id}" not in passo_iss.endpoint


@pytest.mark.asyncio
async def test_welcome_digest_optin_propagado_ao_resultado() -> None:
    empresa = _empresa()
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out_true = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=True,
    )

    session2 = _session_com(empresa=empresa)
    out_false = await service.executar(
        session2,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert out_true.welcome_digest_optin is True
    assert out_false.welcome_digest_optin is False


@pytest.mark.asyncio
async def test_perfil_ui_propagado_para_o_output() -> None:
    empresa = _empresa(perfil_ui="lucro_presumido")
    session = _session_com(empresa=empresa)
    service = OnboardingBundleService(contabil_service=_mock_contabil_service())

    out = await service.executar(
        session,
        tenant_id=uuid4(),
        empresa_id=empresa.id,
        valid_from=date(2026, 1, 1),
        welcome_digest_optin=False,
    )

    assert out.perfil_ui == PerfilUI.LUCRO_PRESUMIDO
    assert out.empresa_id == empresa.id
