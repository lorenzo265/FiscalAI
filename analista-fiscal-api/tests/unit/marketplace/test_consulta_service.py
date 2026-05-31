"""Testes do ConsultaService — ciclo de vida da consulta (Sprint 13 PR2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.marketplace.consulta_service import (
    ConsultaService,
    _hash_pergunta,
    _idempotency_key,
)
from app.shared.exceptions import (
    ConsentimentoAusente,
    ConsultaForaDeFluxo,
    ConsultaJaAvaliada,
    ConsultaNaoEncontrada,
    ConsultaSlaExpirado,
    EmpresaNaoEncontrada,
    ParceiroIndisponivel,
)

_TZ = ZoneInfo("America/Sao_Paulo")


def _empresa(uf: str | None = "SP") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        razao_social="Loja Teste LTDA",
        nome_fantasia=None,
        cnpj="12345678000195",
        regime_tributario="simples_nacional",
        perfil_ui="sn_sem_funcionarios",
        anexo_simples="I",
        cnae_principal="4711301",
        municipio="São Paulo",
        uf=uf,
        faturamento_12m=Decimal("500000.00"),
    )


def _parceiro(
    *,
    ativo: bool = True,
    especialidades: list[str] | None = None,
    crc_status: str = "ativo",
    uf_atuacao: list[str] | None = None,
    rating: Decimal | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        nome="Joana",
        crc_numero="123",
        crc_uf="SP",
        crc_status=crc_status,
        especialidades=especialidades or ["tributario", "contencioso"],
        uf_atuacao=uf_atuacao,
        rating_medio=rating,
        total_consultas=0,
        taxa_resposta_horas=None,
        sla_resposta_horas=24,
        oab_numero=None,
        ativo=ativo,
    )


def _consulta(
    *,
    contador_id: uuid.UUID | None = None,
    status: str = "aberta",
    rating: int | None = None,
    sla_aceitar_em_horas: int = 4,
    sla_responder_em_horas: int = 24,
) -> SimpleNamespace:
    agora = datetime.now(tz=_TZ)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        contador_id=contador_id,
        categoria="consulta_rapida",
        pergunta="Como funciona o Fator R?",
        pergunta_hash="0" * 64,
        contexto_empresa_jsonb={},
        snapshot_versao="v1",
        consentimento_compartilhamento=True,
        consentimento_revogado_em=None,
        pii_apagado_em=None,
        status=status,
        valor_consulta=Decimal("80.00"),
        comissao_plataforma=Decimal("24.00"),
        resposta_resumo=None,
        arquivos_anexos=None,
        rating_cliente=rating,
        comentario_cliente=None,
        idempotency_key=uuid.uuid4(),
        sla_aceitar_ate=agora + timedelta(hours=sla_aceitar_em_horas),
        sla_responder_ate=agora + timedelta(hours=sla_responder_em_horas),
        aberta_em=agora,
        aceita_em=None,
        respondida_em=None,
        paga_em=None,
    )


# ── helpers puros ────────────────────────────────────────────────────────────


def test_hash_pergunta_deterministico() -> None:
    eid = uuid.uuid4()
    h1 = _hash_pergunta(eid, "consulta_rapida", "Como pagar DAS?")
    h2 = _hash_pergunta(eid, "consulta_rapida", "Como pagar DAS?")
    assert h1 == h2
    assert len(h1) == 64


def test_hash_pergunta_trim_no_input() -> None:
    eid = uuid.uuid4()
    assert _hash_pergunta(eid, "x", "abc") == _hash_pergunta(eid, "x", "  abc  ")


def test_idempotency_key_estavel_no_mesmo_dia() -> None:
    eid = uuid.uuid4()
    h = "a" * 64
    from datetime import date
    k1 = _idempotency_key(eid, "consulta_rapida", h, date(2026, 5, 21))
    k2 = _idempotency_key(eid, "consulta_rapida", h, date(2026, 5, 21))
    assert k1 == k2


def test_idempotency_key_muda_no_dia_seguinte() -> None:
    eid = uuid.uuid4()
    h = "a" * 64
    from datetime import date
    k1 = _idempotency_key(eid, "consulta_rapida", h, date(2026, 5, 21))
    k2 = _idempotency_key(eid, "consulta_rapida", h, date(2026, 5, 22))
    assert k1 != k2


# ── criar ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_criar_sem_consentimento_levanta() -> None:
    session = AsyncMock()
    with pytest.raises(ConsentimentoAusente):
        await ConsultaService().criar(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=uuid.uuid4(),
            usuario_id=uuid.uuid4(),
            categoria="consulta_rapida",
            pergunta="Pergunta x",
            consentimento=False,
        )


@pytest.mark.asyncio
async def test_criar_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.marketplace.consulta_service.EmpresaRepo",
        return_value=empresa_repo,
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await ConsultaService().criar(
                session,
                tenant_id=uuid.uuid4(),
                empresa_id=uuid.uuid4(),
                usuario_id=uuid.uuid4(),
                categoria="consulta_rapida",
                pergunta="Pergunta",
                consentimento=True,
            )


@pytest.mark.asyncio
async def test_criar_sem_contador_status_aberta() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    consulta_repo = AsyncMock()
    consulta_inserida = _consulta(status="aberta")
    consulta_repo.inserir_idempotente = AsyncMock(return_value=consulta_inserida)

    with (
        patch(
            "app.modules.marketplace.consulta_service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
    ):
        out = await ConsultaService().criar(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=empresa.id,
            usuario_id=uuid.uuid4(),
            categoria="consulta_rapida",
            pergunta="Como funciona Fator R?",
            consentimento=True,
        )

    consulta_repo.inserir_idempotente.assert_awaited_once()
    values = consulta_repo.inserir_idempotente.call_args[0][0]
    assert values["status"] == "aberta"
    assert values["contador_id"] is None
    assert values["valor_consulta"] == Decimal("80.00")
    assert values["comissao_plataforma"] == Decimal("24.00")
    assert values["snapshot_versao"] == "v1"
    assert values["pergunta_hash"] != ""
    assert out is consulta_inserida


@pytest.mark.asyncio
async def test_criar_com_contador_apto_status_atribuida() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    empresa = _empresa(uf="SP")
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    parceiro = _parceiro(especialidades=["tributario"], uf_atuacao=["SP"])
    parceiro_repo = AsyncMock()
    parceiro_repo.por_id = AsyncMock(return_value=parceiro)

    consulta_repo = AsyncMock()
    consulta_repo.inserir_idempotente = AsyncMock(
        return_value=_consulta(status="atribuida", contador_id=parceiro.id)
    )

    with (
        patch(
            "app.modules.marketplace.consulta_service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
    ):
        await ConsultaService().criar(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=empresa.id,
            usuario_id=uuid.uuid4(),
            categoria="consulta_rapida",
            pergunta="Pergunta",
            consentimento=True,
            contador_id=parceiro.id,
        )

    values = consulta_repo.inserir_idempotente.call_args[0][0]
    assert values["status"] == "atribuida"
    assert values["contador_id"] == parceiro.id


@pytest.mark.asyncio
async def test_criar_com_contador_sem_especialidade_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    # Holding pede especialidade "societario" — parceiro só tem tributario
    parceiro = _parceiro(especialidades=["tributario"])
    parceiro_repo = AsyncMock()
    parceiro_repo.por_id = AsyncMock(return_value=parceiro)

    with (
        patch(
            "app.modules.marketplace.consulta_service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
    ):
        with pytest.raises(ParceiroIndisponivel, match="especialidade"):
            await ConsultaService().criar(
                session,
                tenant_id=uuid.uuid4(),
                empresa_id=empresa.id,
                usuario_id=uuid.uuid4(),
                categoria="holding",
                pergunta="Holding patrimonial?",
                consentimento=True,
                contador_id=parceiro.id,
            )


@pytest.mark.asyncio
async def test_criar_valor_abaixo_do_minimo_eh_corrigido() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    consulta_repo = AsyncMock()
    consulta_repo.inserir_idempotente = AsyncMock(return_value=_consulta())

    with (
        patch(
            "app.modules.marketplace.consulta_service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
    ):
        await ConsultaService().criar(
            session,
            tenant_id=uuid.uuid4(),
            empresa_id=empresa.id,
            usuario_id=uuid.uuid4(),
            categoria="consulta_rapida",
            pergunta="Pergunta",
            consentimento=True,
            valor_consulta=Decimal("10.00"),  # abaixo do preco_base=80
        )

    values = consulta_repo.inserir_idempotente.call_args[0][0]
    assert values["valor_consulta"] == Decimal("80.00")


# ── aceitar ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aceitar_consulta_inexistente_levanta() -> None:
    session = AsyncMock()
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=None)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConsultaNaoEncontrada):
            await ConsultaService().aceitar(
                session, consulta_id=uuid.uuid4(), contador_id=uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_aceitar_contador_errado_levanta() -> None:
    session = AsyncMock()
    consulta = _consulta(status="atribuida", contador_id=uuid.uuid4())
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConsultaForaDeFluxo, match="não está atribuída"):
            await ConsultaService().aceitar(
                session, consulta_id=consulta.id, contador_id=uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_aceitar_status_invalido_levanta() -> None:
    session = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="concluida", contador_id=contador_id)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConsultaForaDeFluxo, match="status 'concluida'"):
            await ConsultaService().aceitar(
                session, consulta_id=consulta.id, contador_id=contador_id
            )


@pytest.mark.asyncio
async def test_aceitar_sla_expirado_levanta() -> None:
    session = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(
        status="atribuida",
        contador_id=contador_id,
        sla_aceitar_em_horas=-1,  # já passou
    )
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConsultaSlaExpirado):
            await ConsultaService().aceitar(
                session, consulta_id=consulta.id, contador_id=contador_id
            )


@pytest.mark.asyncio
async def test_aceitar_sucesso_flipa_status_e_timestamp() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="atribuida", contador_id=contador_id)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        out = await ConsultaService().aceitar(
            session, consulta_id=consulta.id, contador_id=contador_id
        )

    assert out.status == "aceita"
    assert out.aceita_em is not None


# ── responder ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_responder_sucesso_concluida_e_anexos_serializados() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="aceita", contador_id=contador_id)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        out = await ConsultaService().responder(
            session,
            consulta_id=consulta.id,
            contador_id=contador_id,
            resposta_resumo="Tudo certo, segue parecer.",
            arquivos_anexos=[{"nome": "parecer.pdf", "url": "s3://x"}],
        )

    assert out.status == "concluida"
    assert out.respondida_em is not None
    assert out.resposta_resumo == "Tudo certo, segue parecer."
    assert out.arquivos_anexos == {"itens": [{"nome": "parecer.pdf", "url": "s3://x"}]}


@pytest.mark.asyncio
async def test_responder_status_aberta_levanta() -> None:
    session = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="atribuida", contador_id=contador_id)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.set_contador_id",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConsultaForaDeFluxo):
            await ConsultaService().responder(
                session,
                consulta_id=consulta.id,
                contador_id=contador_id,
                resposta_resumo="x" * 20,
            )


# ── avaliar ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_avaliar_rating_fora_de_faixa_levanta() -> None:
    session = AsyncMock()
    with pytest.raises(ConsultaForaDeFluxo):
        await ConsultaService().avaliar(session, consulta_id=uuid.uuid4(), rating=0)
    with pytest.raises(ConsultaForaDeFluxo):
        await ConsultaService().avaliar(session, consulta_id=uuid.uuid4(), rating=6)


@pytest.mark.asyncio
async def test_avaliar_sucesso_recalcula_rating_parceiro() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="concluida", contador_id=contador_id)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    consulta_repo.avaliacoes_recentes = AsyncMock(return_value=[5, 4, 5, 3])

    parceiro = _parceiro()
    parceiro.total_consultas = 7
    parceiro_repo = AsyncMock()
    parceiro_repo.por_id = AsyncMock(return_value=parceiro)

    with (
        patch(
            "app.modules.marketplace.consulta_service.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch(
            "app.modules.marketplace.consulta_service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
    ):
        out = await ConsultaService().avaliar(
            session, consulta_id=consulta.id, rating=5, comentario="ótimo"
        )

    assert out.rating_cliente == 5
    assert parceiro.total_consultas == 8  # incrementou
    assert parceiro.rating_medio == Decimal("4.25")  # (5+4+5+3)/4


@pytest.mark.asyncio
async def test_avaliar_ja_avaliada_levanta() -> None:
    session = AsyncMock()
    contador_id = uuid.uuid4()
    consulta = _consulta(status="concluida", contador_id=contador_id, rating=4)
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with patch(
        "app.modules.marketplace.consulta_service.ConsultaRepo",
        return_value=consulta_repo,
    ):
        with pytest.raises(ConsultaJaAvaliada):
            await ConsultaService().avaliar(
                session, consulta_id=consulta.id, rating=5
            )


@pytest.mark.asyncio
async def test_avaliar_consulta_nao_concluida_levanta() -> None:
    session = AsyncMock()
    consulta = _consulta(status="aceita", contador_id=uuid.uuid4())
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with patch(
        "app.modules.marketplace.consulta_service.ConsultaRepo",
        return_value=consulta_repo,
    ):
        with pytest.raises(ConsultaForaDeFluxo):
            await ConsultaService().avaliar(
                session, consulta_id=consulta.id, rating=4
            )
