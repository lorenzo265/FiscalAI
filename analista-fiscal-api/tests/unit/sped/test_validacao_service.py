"""Testes do SpedValidacaoService — orquestração de validação (Sprint 16 PR3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.sped.ecd.gerador import (
    ContaPlano,
    EntradaEcd,
    IdentificacaoEmpresaEcd,
    LancamentoEcd,
    LinhaDemonstracao,
    PartidaLanc,
    SaldoPeriodico,
    SaldoPeriodicoConta,
    SaldoResultadoConta,
    gerar_ecd,
)
from app.modules.sped.validacao_service import SpedValidacaoService
from app.shared.exceptions import ArquivoSpedNaoEncontrado


def _ecd_perfeita_bytes() -> bytes:
    """Constrói uma ECD perfeita via gerador puro (passa no validador)."""
    plano = (
        ContaPlano(
            codigo="1.1.1.01", descricao="Caixa", natureza="D", nivel=4,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="1.01.01.01.01.01",
        ),
        ContaPlano(
            codigo="4.1.01", descricao="Receita", natureza="C", nivel=3,
            tipo_conta="A", codigo_pai=None,
            codigo_ecd_referencial="4.01.01.01.01.01",
        ),
    )
    lanc = LancamentoEcd(
        numero="1",
        data=date(2025, 3, 15),
        valor_total=Decimal("1000.00"),
        indicador_origem="N",
        partidas=(
            PartidaLanc(
                codigo_conta="1.1.1.01", valor=Decimal("1000.00"),
                indicador_dc="D", historico="x",
            ),
            PartidaLanc(
                codigo_conta="4.1.01", valor=Decimal("1000.00"),
                indicador_dc="C", historico="x",
            ),
        ),
    )
    entrada = EntradaEcd(
        empresa=IdentificacaoEmpresaEcd(
            cnpj="12345678000190", razao_social="X LTDA",
            nome_fantasia=None, uf="SP", municipio=None,
            codigo_municipio_ibge="3550308",
        ),
        ano_calendario=2025,
        inicio_exercicio=date(2025, 1, 1),
        fim_exercicio=date(2025, 12, 31),
        plano_contas=plano,
        saldos_periodicos=(
            SaldoPeriodico(
                inicio=date(2025, 3, 1), fim=date(2025, 3, 31),
                saldos=(
                    SaldoPeriodicoConta(
                        codigo_conta="1.1.1.01",
                        saldo_inicial=Decimal("0"),
                        indicador_saldo_inicial="D",
                        total_debitos=Decimal("1000.00"),
                        total_creditos=Decimal("0"),
                        saldo_final=Decimal("1000.00"),
                        indicador_saldo_final="D",
                    ),
                ),
            ),
        ),
        lancamentos=(lanc,),
        saldos_resultado_antes_encerramento=(
            SaldoResultadoConta(
                codigo_conta="4.1.01", valor=Decimal("1000.00"),
                indicador_dc="C",
            ),
        ),
        balanco=(
            LinhaDemonstracao("1", 1, "D", "ATIVO TOTAL", Decimal("1000.00")),
        ),
        dre=(
            LinhaDemonstracao("3.01", 2, "C", "Receita Bruta", Decimal("1000.00")),
        ),
    )
    return gerar_ecd(entrada).conteudo


def _arquivo_sped(
    empresa_id: uuid.UUID,
    tipo: str = "ecd",
    *,
    status: str = "gerado",
    conteudo: bytes | None = None,
) -> SimpleNamespace:
    bytes_ = conteudo if conteudo is not None else _ecd_perfeita_bytes()
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo=tipo,
        periodo_inicio=date(2025, 1, 1),
        periodo_fim=date(2025, 12, 31),
        conteudo_bytea=bytes_,
        tamanho_bytes=len(bytes_),
        hash_arquivo="0" * 64,
        storage_key=None,
        recibo_transmissao=None,
        status=status,
        validacao_jsonb=None,
        algoritmo_versao="sped.ecd.v2",
        gerado_por_usuario_id=None,
        supersedes=None,
        superseded_by=None,
        gerado_em=datetime(2026, 1, 5),
        transmitido_em=None,
    )


@pytest.mark.asyncio
async def test_validar_arquivo_ok_transita_status_para_validado() -> None:
    """Arquivo sem erros: status='gerado' → 'validado'."""
    empresa_id = uuid.uuid4()
    arquivo = _arquivo_sped(empresa_id, "ecd")
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=arquivo)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ):
        executada = await SpedValidacaoService().validar(
            session, empresa_id, arquivo.id, tipo="ecd",
        )
    assert executada.resultado.ok
    assert arquivo.status == "validado"
    assert arquivo.validacao_jsonb is not None
    assert arquivo.validacao_jsonb["ok"] is True


@pytest.mark.asyncio
async def test_validar_arquivo_com_erros_mantem_status_gerado() -> None:
    """Arquivo com erros estruturais: status permanece 'gerado'."""
    empresa_id = uuid.uuid4()
    # Conteúdo malformado (sem 9999).
    arquivo = _arquivo_sped(empresa_id, "ecd", conteudo=b"|0000|10.00|\n")
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=arquivo)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ):
        executada = await SpedValidacaoService().validar(
            session, empresa_id, arquivo.id, tipo="ecd",
        )
    assert not executada.resultado.ok
    assert arquivo.status == "gerado"  # não promovido
    assert arquivo.validacao_jsonb is not None
    assert arquivo.validacao_jsonb["ok"] is False
    assert arquivo.validacao_jsonb["total_erros"] >= 1


@pytest.mark.asyncio
async def test_validar_id_inexistente_levanta_404() -> None:
    empresa_id = uuid.uuid4()
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ), pytest.raises(ArquivoSpedNaoEncontrado):
        await SpedValidacaoService().validar(
            session, empresa_id, uuid.uuid4(), tipo="ecd",
        )


@pytest.mark.asyncio
async def test_validar_cross_empresa_levanta_404() -> None:
    """Defesa em profundidade — outro tenant via RLS já filtra, mas
    cross-empresa dentro do mesmo tenant também é negado pelo service."""
    empresa_a = uuid.uuid4()
    empresa_b = uuid.uuid4()
    arquivo = _arquivo_sped(empresa_a, "ecd")
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=arquivo)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ), pytest.raises(ArquivoSpedNaoEncontrado):
        await SpedValidacaoService().validar(
            session, empresa_b, arquivo.id, tipo="ecd",
        )


@pytest.mark.asyncio
async def test_validar_tipo_divergente_levanta_404() -> None:
    """Pedir validar ECF mas arquivo é ECD."""
    empresa_id = uuid.uuid4()
    arquivo = _arquivo_sped(empresa_id, "ecd")
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=arquivo)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ), pytest.raises(ArquivoSpedNaoEncontrado):
        await SpedValidacaoService().validar(
            session, empresa_id, arquivo.id, tipo="ecf",
        )


@pytest.mark.asyncio
async def test_validar_idempotente_sobrescreve_jsonb() -> None:
    """Chamadas repetidas atualizam validacao_jsonb (não acumulam)."""
    empresa_id = uuid.uuid4()
    arquivo = _arquivo_sped(empresa_id, "ecd")
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=arquivo)
    with patch(
        "app.modules.sped.validacao_service.ArquivoSpedRepo",
        return_value=repo,
    ):
        await SpedValidacaoService().validar(
            session, empresa_id, arquivo.id, tipo="ecd",
        )
        primeiro_jsonb = arquivo.validacao_jsonb
        await SpedValidacaoService().validar(
            session, empresa_id, arquivo.id, tipo="ecd",
        )
        segundo_jsonb = arquivo.validacao_jsonb
    # Conteúdo é determinístico para o mesmo arquivo.
    assert primeiro_jsonb == segundo_jsonb
