"""Testes unitários do PgdasService + helpers puros (Sprint 6 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.pgdas.schemas import TransmissaoStatus
from app.modules.pgdas.service import (
    PgdasService,
    _extrair_protocolo_e_recibo,
    _gerar_idempotency_key,
    _montar_payload_declaracao,
)
from app.shared.exceptions import (
    ApuracaoNaoEncontrada,
    EmpresaNaoEncontrada,
    RegimeIncompativel,
    SerproErro,
)


def _empresa_sn() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        cnpj="12345678000195",
        regime_tributario="simples_nacional",
        anexo_simples="III",
        municipio="3550308",
        uf="SP",
    )


def _apuracao_das(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        competencia=date(2026, 4, 1),
        tipo="das",
        output_jsonb={
            "anexo": "III",
            "anexo_efetivo": "III",
            "receita_mes": "10000.00",
            "valor_das": "650.00",
        },
        transmitido_em=None,
        status="calculado",
    )


# ── helpers puros ────────────────────────────────────────────────────────────


class TestGerarIdempotencyKey:
    def test_deterministico_mesmos_inputs(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        k1 = _gerar_idempotency_key(eid, c, 1, False)
        k2 = _gerar_idempotency_key(eid, c, 1, False)
        assert k1 == k2

    def test_retificadora_muda_key(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        original = _gerar_idempotency_key(eid, c, 1, False)
        retif = _gerar_idempotency_key(eid, c, 1, True)
        assert original != retif

    def test_tentativa_diferente_muda_key(self) -> None:
        eid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        c = date(2026, 4, 1)
        k1 = _gerar_idempotency_key(eid, c, 1, False)
        k2 = _gerar_idempotency_key(eid, c, 2, False)
        assert k1 != k2


class TestMontarPayload:
    def test_estrutura_basica(self) -> None:
        empresa = _empresa_sn()
        apuracao = _apuracao_das(empresa.id)
        payload = _montar_payload_declaracao(empresa, apuracao)
        decl = payload["declaracao"]
        assert decl["tipoDeclaracao"] == 1
        assert decl["receitaPaCompetencia"] == "10000.00"
        assert decl["estabelecimentos"][0]["cnpjCompleto"] == "12345678000195"
        atividade = decl["estabelecimentos"][0]["atividades"][0]
        assert atividade["idAtividade"] == 3  # Anexo III
        assert atividade["valorAtividade"] == "10000.00"

    def test_anexo_i_mapeia_comercio(self) -> None:
        empresa = _empresa_sn()
        empresa.anexo_simples = "I"
        apuracao = _apuracao_das(empresa.id)
        apuracao.output_jsonb["anexo_efetivo"] = "I"
        payload = _montar_payload_declaracao(empresa, apuracao)
        ativ = payload["declaracao"]["estabelecimentos"][0]["atividades"][0]
        assert ativ["idAtividade"] == 1


class TestExtrairProtocolo:
    def test_dados_dict(self) -> None:
        resposta = {"dados": {"numeroDeclaracao": "ABC-001"}}
        protocolo, _ = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "ABC-001"

    def test_dados_string_json(self) -> None:
        resposta = {"dados": '{"numeroDeclaracao": "ABC-002"}'}
        protocolo, _ = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "ABC-002"

    def test_sem_protocolo(self) -> None:
        protocolo, _ = _extrair_protocolo_e_recibo({"dados": {}})
        assert protocolo is None

    def test_com_recibo_b64_gera_storage_key(self) -> None:
        resposta = {"dados": {"numeroDeclaracao": "001", "recibo": "JVB="}}
        protocolo, recibo = _extrair_protocolo_e_recibo(resposta)
        assert protocolo == "001"
        assert recibo == "pgdas/001.pdf"


# ── service.transmitir ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo):
        with pytest.raises(EmpresaNaoEncontrada):
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                uuid.uuid4(),
                date(2026, 4, 1),
                eh_retificadora=False,
                serpro_client=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_transmitir_regime_lp_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()
    empresa.regime_tributario = "lucro_presumido"
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo):
        with pytest.raises(RegimeIncompativel):
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                empresa.id,
                date(2026, 4, 1),
                eh_retificadora=False,
                serpro_client=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_transmitir_sem_apuracao_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=None)

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo",
            return_value=apuracao_repo,
        ),
    ):
        with pytest.raises(ApuracaoNaoEncontrada):
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                empresa.id,
                date(2026, 4, 1),
                eh_retificadora=False,
                serpro_client=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_transmissao_sucesso_atualiza_apuracao() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    tr_id = uuid.uuid4()
    transmissoes = AsyncMock()
    transmissoes.proxima_tentativa = AsyncMock(return_value=1)
    transmissoes.criar = AsyncMock(return_value=SimpleNamespace(id=tr_id))
    transmissoes.marcar_sucesso = AsyncMock()

    serpro = AsyncMock()
    serpro.transmitir_pgdas_d = AsyncMock(
        return_value={"dados": {"numeroDeclaracao": "PGDAS-2026-04-001"}}
    )

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        out = await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            apuracao.competencia,
            eh_retificadora=False,
            serpro_client=serpro,
        )

    assert out.status == TransmissaoStatus.TRANSMITIDA
    assert out.protocolo == "PGDAS-2026-04-001"
    assert apuracao.status == "transmitida"
    assert apuracao.transmitido_em is not None
    transmissoes.marcar_sucesso.assert_awaited_once()


@pytest.mark.asyncio
async def test_transmissao_falha_serpro_marca_erro() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    transmissoes = AsyncMock()
    transmissoes.proxima_tentativa = AsyncMock(return_value=1)
    transmissoes.criar = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    transmissoes.marcar_erro = AsyncMock()

    serpro = AsyncMock()
    serpro.transmitir_pgdas_d = AsyncMock(side_effect=SerproErro("422 inválido"))

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        out = await PgdasService().transmitir(
            session,
            uuid.uuid4(),
            empresa.id,
            apuracao.competencia,
            eh_retificadora=False,
            serpro_client=serpro,
        )

    assert out.status == TransmissaoStatus.ERRO
    assert out.erro == "SerproErro"
    transmissoes.marcar_erro.assert_awaited_once()
    # Apuração NÃO deve ser marcada como transmitida em caso de erro
    assert apuracao.status == "calculado"


@pytest.mark.asyncio
async def test_retificacao_sem_transmissao_previa_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa_sn()
    apuracao = _apuracao_das(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    apuracao_repo = AsyncMock()
    apuracao_repo.buscar = AsyncMock(return_value=apuracao)

    transmissoes = AsyncMock()
    transmissoes.ultima_transmissao = AsyncMock(return_value=None)

    with (
        patch("app.modules.pgdas.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.pgdas.service.ApuracaoFiscalRepo", return_value=apuracao_repo
        ),
        patch(
            "app.modules.pgdas.service.TransmissoesPgdasRepo",
            return_value=transmissoes,
        ),
    ):
        with pytest.raises(RegimeIncompativel):
            await PgdasService().transmitir(
                session,
                uuid.uuid4(),
                empresa.id,
                apuracao.competencia,
                eh_retificadora=True,
                serpro_client=AsyncMock(),
            )
