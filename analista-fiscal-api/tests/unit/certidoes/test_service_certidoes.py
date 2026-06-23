"""Testes unitários do CertidoesService (Sprint 6 PR1)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.certidoes.schemas import CertidaoStatus, CertidaoTipo
from app.modules.certidoes.service import (
    CertidoesService,
    _gerar_idempotency_key,
    _parse_resposta_cnd,
)
from app.shared.exceptions import EmpresaNaoEncontrada, SerproErro

# ── helpers puros ────────────────────────────────────────────────────────────


class TestGerarIdempotencyKey:
    def test_deterministico_no_mesmo_dia(self) -> None:
        empresa_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        k1 = _gerar_idempotency_key(empresa_id, "cnd")
        k2 = _gerar_idempotency_key(empresa_id, "cnd")
        assert k1 == k2

    def test_diferentes_empresas_geram_keys_diferentes(self) -> None:
        e1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        e2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        assert _gerar_idempotency_key(e1, "cnd") != _gerar_idempotency_key(e2, "cnd")


class TestParseRespostaCnd:
    def test_payload_dados_aninhado(self) -> None:
        resposta = {"dados": {"numero": "1234", "situacao": "Negativa"}}
        numero, status, pdf = _parse_resposta_cnd(resposta)
        assert numero == "1234"
        assert status == CertidaoStatus.NEGATIVA.value
        assert pdf is None

    def test_dados_string_json(self) -> None:
        resposta = {"dados": '{"numero": "5678", "situacao": "Positiva com efeitos de negativa"}'}
        numero, status, _ = _parse_resposta_cnd(resposta)
        assert numero == "5678"
        assert status == CertidaoStatus.POSITIVA_COM_EFEITOS_DE_NEGATIVA.value

    def test_positiva_pura(self) -> None:
        resposta = {"dados": {"numero": "X", "situacao": "Positiva"}}
        _, status, _ = _parse_resposta_cnd(resposta)
        assert status == CertidaoStatus.POSITIVA.value

    def test_formato_inesperado_cai_em_emitida(self) -> None:
        resposta = {"qualquer_coisa": True}
        numero, status, _ = _parse_resposta_cnd(resposta)
        assert numero is None
        assert status == CertidaoStatus.EMITIDA.value

    def test_pdf_base64_extraido(self) -> None:
        resposta = {"dados": {"situacao": "Negativa", "pdfBase64": "JVBERi0xLjQK"}}
        _, _, pdf = _parse_resposta_cnd(resposta)
        assert pdf == "JVBERi0xLjQK"


# ── service.emitir ───────────────────────────────────────────────────────────


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


@pytest.mark.asyncio
async def test_emitir_cnd_sucesso_persiste_negativa() -> None:
    empresa = _empresa()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    serpro = AsyncMock()
    serpro.emitir_certidao_cnd = AsyncMock(
        return_value={"dados": {"numero": "CND-001", "situacao": "Negativa"}}
    )

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    cert_id = uuid.uuid4()
    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=cert_id,
            numero="CND-001",
            status=CertidaoStatus.NEGATIVA.value,
            valid_until=None,
        )
    )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session, tenant_id, empresa.id, CertidaoTipo.CND, serpro_client=serpro
        )

    assert out.status == CertidaoStatus.NEGATIVA
    assert out.numero == "CND-001"
    serpro.emitir_certidao_cnd.assert_awaited_once()
    chamada = repo_mock.criar.await_args
    assert chamada.kwargs["status"] == CertidaoStatus.NEGATIVA.value
    assert chamada.kwargs["valid_until"] is not None  # 180 dias adicionados


@pytest.mark.asyncio
async def test_emitir_cnd_falha_serpro_persiste_erro() -> None:
    empresa = _empresa()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    serpro = AsyncMock()
    serpro.emitir_certidao_cnd = AsyncMock(side_effect=SerproErro("503 down"))

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            numero=None,
            status=CertidaoStatus.ERRO.value,
            valid_until=None,
        )
    )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session, tenant_id, empresa.id, CertidaoTipo.CND, serpro_client=serpro
        )

    assert out.status == CertidaoStatus.ERRO
    chamada = repo_mock.criar.await_args
    assert chamada.kwargs["status"] == CertidaoStatus.ERRO.value
    assert "erro" in chamada.kwargs["payload_json"]


@pytest.mark.asyncio
async def test_emitir_crf_registra_processando_skeleton() -> None:
    empresa = _empresa()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            numero=None,
            status=CertidaoStatus.PROCESSANDO.value,
            valid_until=None,
        )
    )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session, tenant_id, empresa.id, CertidaoTipo.CRF, serpro_client=None
        )

    assert out.status == CertidaoStatus.PROCESSANDO
    chamada = repo_mock.criar.await_args
    assert chamada.kwargs["tipo"] == CertidaoTipo.CRF.value


@pytest.mark.asyncio
async def test_emitir_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)

    with patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo), pytest.raises(EmpresaNaoEncontrada):
        await CertidoesService().emitir(
            session, uuid.uuid4(), uuid.uuid4(), CertidaoTipo.CND, serpro_client=AsyncMock()
        )


# ── Sprint 19.6 PR1 (#3) — refactor CRF/CNDT scrapers ──────────────────────


from datetime import date  # noqa: E402

from app.modules.certidoes.scrapers import (  # noqa: E402
    CertidaoExtraida,
    NotImplementedScraper,
)
from app.shared.exceptions import CertidaoEmissaoFalhou  # noqa: E402


@pytest.mark.asyncio
async def test_crf_sem_scraper_configurado_cai_em_processando() -> None:
    """Service sem scraper injetado mantém comportamento legado."""
    empresa = _empresa()
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            numero=None,
            status=CertidaoStatus.PROCESSANDO.value,
            valid_until=None,
        )
    )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session,
            uuid.uuid4(),
            empresa.id,
            CertidaoTipo.CRF,
            serpro_client=None,
            crf_scraper=None,
        )
    assert out.status == CertidaoStatus.PROCESSANDO
    assert "manualmente" in out.mensagem.lower()


@pytest.mark.asyncio
async def test_crf_com_not_implemented_scraper_persiste_erro() -> None:
    """``NotImplementedScraper`` levanta ``CertidaoEmissaoFalhou`` → status='erro'."""
    empresa = _empresa()
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            numero=None,
            status=CertidaoStatus.ERRO.value,
            valid_until=None,
        )
    )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session,
            uuid.uuid4(),
            empresa.id,
            CertidaoTipo.CRF,
            serpro_client=None,
            crf_scraper=NotImplementedScraper(tipo="CRF"),
        )
    assert out.status == CertidaoStatus.ERRO
    chamada = repo_mock.criar.await_args
    assert chamada.kwargs["status"] == CertidaoStatus.ERRO.value


@pytest.mark.asyncio
async def test_crf_com_scraper_real_sucesso_persiste_negativa() -> None:
    """Scraper que devolve ``CertidaoExtraida`` válida → status='negativa'."""
    empresa = _empresa()
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo_mock = AsyncMock()
    repo_mock.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            numero="CRF-2026-001",
            status=CertidaoStatus.NEGATIVA.value,
            valid_until=date(2026, 7, 27),
        )
    )

    class _FakeCrfScraper:
        async def emitir(
            self, cnpj: str, *, idempotency_key: str
        ) -> CertidaoExtraida:
            return CertidaoExtraida(
                numero="CRF-2026-001",
                valid_until=date(2026, 7, 27),
                status_normalizado=CertidaoStatus.NEGATIVA.value,
                pdf_base64=None,
            )

    with (
        patch("app.modules.certidoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.certidoes.service.CertidoesRepo", return_value=repo_mock),
    ):
        out = await CertidoesService().emitir(
            session,
            uuid.uuid4(),
            empresa.id,
            CertidaoTipo.CRF,
            serpro_client=None,
            crf_scraper=_FakeCrfScraper(),
        )
    assert out.status == CertidaoStatus.NEGATIVA
    assert out.numero == "CRF-2026-001"
    chamada = repo_mock.criar.await_args
    assert chamada.kwargs["status"] == CertidaoStatus.NEGATIVA.value
    assert chamada.kwargs["valid_until"] == date(2026, 7, 27)


@pytest.mark.asyncio
async def test_not_implemented_scraper_levanta_certidao_emissao_falhou() -> None:
    """Smoke test do adapter padrão — direto, sem service."""
    scraper = NotImplementedScraper(tipo="CRF")
    with pytest.raises(CertidaoEmissaoFalhou, match="não configurado"):
        await scraper.emitir("12345678000195", idempotency_key="x")
