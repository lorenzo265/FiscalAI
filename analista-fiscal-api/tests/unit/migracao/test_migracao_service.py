"""Testes do MigracaoService — validações cruzadas + idempotência (Sprint 18 PR2).

Foco nas validações que rodam ANTES da escrita no DB (parser puro +
checagens contra ``Empresa``) — o caminho feliz de persistência é coberto
pelo pipeline integration test (e implicitamente pelos round-trips dos
parsers).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.migracao.service import (
    PERIODO_INICIO_MINIMO,
    MigracaoService,
)
from app.modules.sped.ecd.gerador import gerar_ecd
from app.shared.exceptions import (
    EmpresaCnpjDivergente,
    EmpresaNaoEncontrada,
    PeriodoForaCobertura,
    SpedInvalido,
)

# Reusa helpers já configurados.
from tests.unit.sped.test_ecd_gerador import (
    _entrada_minima as _entrada_sped16,
)

# ── Fixtures auxiliares ─────────────────────────────────────────────────────


def _empresa_db(cnpj: str = "12345678000190") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj=cnpj)


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.migracao.service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(EmpresaNaoEncontrada):
        await MigracaoService().importar_sped_ecd(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=b"conteudo qualquer",
            nome_arquivo="sped.txt",
        )


@pytest.mark.asyncio
async def test_arquivo_invalido_levanta_sped_invalido() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa_db())
    with patch(
        "app.modules.migracao.service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(SpedInvalido, match="vazio"):
        await MigracaoService().importar_sped_ecd(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=b"",
            nome_arquivo="sped.txt",
        )


@pytest.mark.asyncio
async def test_cnpj_divergente_levanta_antes_de_qualquer_escrita() -> None:
    """SPED com CNPJ != empresa.cnpj — rejeita sem chamar repos de escrita."""
    session = AsyncMock()
    # Empresa no DB tem CNPJ diferente do SPED gerado (12345678000190).
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(
        return_value=_empresa_db(cnpj="99999999000100")
    )

    arquivo = gerar_ecd(_entrada_sped16())
    with patch(
        "app.modules.migracao.service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(EmpresaCnpjDivergente, match="12345678000190"):
        await MigracaoService().importar_sped_ecd(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=arquivo.conteudo,
            nome_arquivo="sped.txt",
        )

    # Sessão NÃO foi tocada além do read da empresa.
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_periodo_anterior_a_2024_levanta() -> None:
    """Corte 2024-01-01 — período anterior é rejeitado (PeriodoForaCobertura)."""
    # Reusa fixtures do Sprint 16, mas substitui o ano para 2023.
    from app.modules.sped.ecd.gerador import EntradaEcd

    base = _entrada_sped16()
    entrada_2023 = EntradaEcd(
        empresa=base.empresa,
        ano_calendario=2023,
        inicio_exercicio=date(2023, 1, 1),
        fim_exercicio=date(2023, 12, 31),
        plano_contas=base.plano_contas,
        saldos_periodicos=base.saldos_periodicos,
        lancamentos=base.lancamentos,
        saldos_resultado_antes_encerramento=base.saldos_resultado_antes_encerramento,
        balanco=base.balanco,
        dre=base.dre,
    )
    arquivo = gerar_ecd(entrada_2023)

    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa_db())
    with patch(
        "app.modules.migracao.service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(PeriodoForaCobertura, match="2023"):
        await MigracaoService().importar_sped_ecd(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=arquivo.conteudo,
            nome_arquivo="sped.txt",
        )
    # Confirma corte explícito.
    assert date(2024, 1, 1) == PERIODO_INICIO_MINIMO


@pytest.mark.asyncio
async def test_hash_ja_importado_retorna_lote_anterior() -> None:
    """Idempotência §8.9 — re-upload do mesmo arquivo devolve lote anterior."""
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa_db())

    lote_anterior = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        fonte="sped_ecd",
        arquivo_sped_id=uuid.uuid4(),
        nome_arquivo="sped.txt",
        hash_arquivo="abc" * 21 + "a",
        iniciado_em=datetime.now(UTC),
        concluido_em=datetime.now(UTC),
        status="concluido",
        resumo_jsonb={"cnpj_arquivo": "12345678000190"},
        erros_jsonb=None,
        algoritmo_versao="migracao.ecd.v1",
    )

    lote_repo = AsyncMock()
    lote_repo.por_hash_concluido = AsyncMock(return_value=lote_anterior)

    arquivo = gerar_ecd(_entrada_sped16())
    with (
        patch(
            "app.modules.migracao.service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.migracao.service.LoteImportacaoRepo",
            return_value=lote_repo,
        ),
    ):
        resultado = await MigracaoService().importar_sped_ecd(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=arquivo.conteudo,
            nome_arquivo="sped.txt",
        )

    assert resultado.reaproveitado is True
    assert resultado.lote is lote_anterior
    # Não criou arquivo_sped nem novo lote.
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ecf_cnpj_divergente_levanta() -> None:
    """Idem para ECF — validação cruzada antes de tudo."""
    from app.modules.sped.ecf.gerador import gerar_ecf
    from tests.unit.migracao.test_parser_ecf import _entrada as _entrada_ecf

    arquivo = gerar_ecf(_entrada_ecf())
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(
        return_value=_empresa_db(cnpj="99999999000100")
    )
    with patch(
        "app.modules.migracao.service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(EmpresaCnpjDivergente):
        await MigracaoService().importar_sped_ecf(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            conteudo=arquivo.conteudo,
            nome_arquivo="ecf.txt",
        )
