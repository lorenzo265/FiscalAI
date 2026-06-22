"""Testes do ImobilizadoService (Sprint 8 PR1 + fix A4).

Fix A4: coerência taxa × vida útil (IN SRF 162/1998).
  * Ambos informados e coerentes → aceita; taxa é re-derivada de vida_meses.
  * Ambos informados e incoerentes → rejeita com LancamentoInvalido (422).
  * Só taxa → deriva vida útil = round(12 / taxa).
  * Só vida → deriva taxa = 12 / vida_meses.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.imobilizado.schemas import (
    BaixarBemIn,
    CadastrarBemIn,
    CategoriaBem,
)
from app.modules.imobilizado.service import ImobilizadoService
from app.shared.exceptions import (
    BemJaBaixado,
    BemNaoEncontrado,
    EmpresaNaoEncontrada,
    LancamentoInvalido,
    TabelaTributariaAusente,
)


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


def _bem_persistido(
    empresa_id: uuid.UUID,
    *,
    data_baixa: date | None = None,
    ativo: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        descricao="Notebook Dell",
        categoria="computador",
        data_aquisicao=date(2026, 1, 10),
        valor_aquisicao=Decimal("5000.00"),
        taxa_depreciacao_anual=Decimal("0.2000"),
        vida_util_meses=60,
        valor_residual=Decimal("0"),
        metodo_depreciacao="linear",
        documento_fiscal_id=None,
        data_baixa=data_baixa,
        motivo_baixa=None,
        ativo=ativo,
        criado_em=datetime.now(),
    )


# ── cadastrar ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cadastrar_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo
    ), pytest.raises(EmpresaNaoEncontrada):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            CadastrarBemIn(
                descricao="Bem teste",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("5000"),
            ),
        )


@pytest.mark.asyncio
async def test_cadastrar_resolve_taxa_via_tabela_rfb() -> None:
    """Quando taxa e vida não são informadas, o service busca na tabela RFB."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    bem_persistido = _bem_persistido(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    tabela_repo = AsyncMock()
    tabela_repo.taxa_vigente = AsyncMock(
        return_value=SimpleNamespace(
            taxa_anual=Decimal("0.2000"), vida_util_anos=5
        )
    )

    bem_repo = AsyncMock()
    bem_repo.criar = AsyncMock(return_value=bem_persistido)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.TabelaDepreciacaoRepo",
            return_value=tabela_repo,
        ),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
    ):
        out = await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa.id,
            CadastrarBemIn(
                descricao="Notebook Dell",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 10),
                valor_aquisicao=Decimal("5000.00"),
            ),
        )

    chamada = bem_repo.criar.await_args
    assert chamada.kwargs["taxa_depreciacao_anual"] == Decimal("0.2000")
    assert chamada.kwargs["vida_util_meses"] == 60  # 5 anos × 12
    assert out.categoria == CategoriaBem.COMPUTADOR


@pytest.mark.asyncio
async def test_cadastrar_tabela_ausente_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    tabela_repo = AsyncMock()
    tabela_repo.taxa_vigente = AsyncMock(return_value=None)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.TabelaDepreciacaoRepo",
            return_value=tabela_repo,
        ),
        pytest.raises(TabelaTributariaAusente),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa.id,
            CadastrarBemIn(
                descricao="Bem teste",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("5000"),
            ),
        )


@pytest.mark.asyncio
async def test_cadastrar_taxa_informada_pula_tabela() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    bem_persistido = _bem_persistido(empresa.id)

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    tabela_repo = AsyncMock()
    tabela_repo.taxa_vigente = AsyncMock()

    bem_repo = AsyncMock()
    bem_repo.criar = AsyncMock(return_value=bem_persistido)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.TabelaDepreciacaoRepo",
            return_value=tabela_repo,
        ),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa.id,
            CadastrarBemIn(
                descricao="Bem teste",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("5000"),
                taxa_depreciacao_anual=Decimal("0.25"),
                vida_util_meses=48,
            ),
        )

    tabela_repo.taxa_vigente.assert_not_called()
    chamada = bem_repo.criar.await_args
    assert chamada.kwargs["taxa_depreciacao_anual"] == Decimal("0.25")
    assert chamada.kwargs["vida_util_meses"] == 48


# ── baixar ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_baixar_bem_inexistente_levanta() -> None:
    session = AsyncMock()
    bem_repo = AsyncMock()
    bem_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
    ), pytest.raises(BemNaoEncontrado):
        await ImobilizadoService().baixar(
            session,
            uuid.uuid4(),
            uuid.uuid4(),
            BaixarBemIn(data_baixa=date.today(), motivo_baixa="venda"),
        )


@pytest.mark.asyncio
async def test_baixar_bem_outra_empresa_levanta() -> None:
    session = AsyncMock()
    outra = uuid.uuid4()
    bem = _bem_persistido(outra)
    bem_repo = AsyncMock()
    bem_repo.por_id = AsyncMock(return_value=bem)
    with patch(
        "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
    ), pytest.raises(BemNaoEncontrado):
        await ImobilizadoService().baixar(
            session,
            uuid.uuid4(),
            bem.id,
            BaixarBemIn(data_baixa=date.today(), motivo_baixa="venda"),
        )


@pytest.mark.asyncio
async def test_baixar_ja_baixado_levanta() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    bem = _bem_persistido(empresa_id, data_baixa=date(2026, 3, 1))
    bem_repo = AsyncMock()
    bem_repo.por_id = AsyncMock(return_value=bem)
    with patch(
        "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
    ), pytest.raises(BemJaBaixado):
        await ImobilizadoService().baixar(
            session,
            empresa_id,
            bem.id,
            BaixarBemIn(data_baixa=date(2026, 4, 1), motivo_baixa="venda"),
        )


@pytest.mark.asyncio
async def test_baixar_data_anterior_a_aquisicao_levanta() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    bem = _bem_persistido(empresa_id)
    bem.data_aquisicao = date(2026, 6, 1)
    bem_repo = AsyncMock()
    bem_repo.por_id = AsyncMock(return_value=bem)
    with patch(
        "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
    ), pytest.raises(BemJaBaixado, match="anterior"):
        await ImobilizadoService().baixar(
            session,
            empresa_id,
            bem.id,
            BaixarBemIn(data_baixa=date(2026, 5, 30), motivo_baixa="venda"),
        )


@pytest.mark.asyncio
async def test_baixar_sucesso_marca_inativo() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    bem = _bem_persistido(empresa_id)
    bem_repo = AsyncMock()
    bem_repo.por_id = AsyncMock(return_value=bem)

    async def baixar_fake(b, *, data_baixa, motivo):
        b.data_baixa = data_baixa
        b.motivo_baixa = motivo
        b.ativo = False

    bem_repo.baixar = AsyncMock(side_effect=baixar_fake)
    with patch(
        "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
    ):
        out = await ImobilizadoService().baixar(
            session,
            empresa_id,
            bem.id,
            BaixarBemIn(data_baixa=date(2026, 6, 1), motivo_baixa="venda"),
        )

    assert out.ativo is False
    assert out.data_baixa == date(2026, 6, 1)


# ── gerar_depreciacao_mensal ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lote_idempotente_pula_existentes() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    bem = _bem_persistido(empresa.id)
    bem_repo = AsyncMock()
    bem_repo.listar_ativos_depreciaveis = AsyncMock(return_value=[bem])

    depr_repo = AsyncMock()
    depr_repo.existe = AsyncMock(return_value=True)  # já existe
    depr_repo.buscar_acumulado_ate = AsyncMock()
    depr_repo.criar = AsyncMock()

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
        patch(
            "app.modules.imobilizado.service.DepreciacaoRepo",
            return_value=depr_repo,
        ),
    ):
        out = await ImobilizadoService().gerar_depreciacao_mensal(
            session, uuid.uuid4(), empresa.id, date(2026, 2, 1)
        )

    assert out.bens_processados == 1
    assert out.bens_depreciados == 0
    depr_repo.criar.assert_not_called()


@pytest.mark.asyncio
async def test_lote_persiste_parcela_e_acumula() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    bem = _bem_persistido(empresa.id)
    bem_repo = AsyncMock()
    bem_repo.listar_ativos_depreciaveis = AsyncMock(return_value=[bem])

    depr_repo = AsyncMock()
    depr_repo.existe = AsyncMock(return_value=False)
    depr_repo.buscar_acumulado_ate = AsyncMock(return_value=Decimal("0"))
    depr_repo.criar = AsyncMock()

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
        patch(
            "app.modules.imobilizado.service.DepreciacaoRepo",
            return_value=depr_repo,
        ),
    ):
        out = await ImobilizadoService().gerar_depreciacao_mensal(
            session, uuid.uuid4(), empresa.id, date(2026, 2, 1)
        )

    chamada = depr_repo.criar.await_args
    # 5000 / 60 = 83,33
    assert chamada.kwargs["valor_depreciado"] == Decimal("83.33")
    assert out.bens_depreciados == 1
    assert out.valor_total_depreciado == Decimal("83.33")


@pytest.mark.asyncio
async def test_lote_competencia_normalizada_para_dia_1() -> None:
    """Mesmo se o cliente mandar 2026-02-15, persiste como 2026-02-01."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    bem_repo = AsyncMock()
    bem_repo.listar_ativos_depreciaveis = AsyncMock(return_value=[])

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
    ):
        out = await ImobilizadoService().gerar_depreciacao_mensal(
            session, uuid.uuid4(), empresa.id, date(2026, 2, 15)
        )

    assert out.competencia == date(2026, 2, 1)


# ── coerência taxa × vida útil (Fix A4 — IN SRF 162/1998) ───────────────────


def _mock_empresa_e_bem(empresa_id: uuid.UUID) -> tuple[AsyncMock, AsyncMock]:
    """Helper: empresa_repo + bem_repo prontos para testes de cadastro."""
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(
        return_value=SimpleNamespace(id=empresa_id, cnpj="12345678000195")
    )
    bem_repo = AsyncMock()
    bem_repo.criar = AsyncMock(return_value=_bem_persistido(empresa_id))
    return empresa_repo, bem_repo


@pytest.mark.asyncio
async def test_coerencia_taxa_20pct_vida_60_meses_aceita() -> None:
    """taxa=20% + vida=60 meses → coerentes (12/60=0.2); deve aceitar."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    empresa_repo, bem_repo = _mock_empresa_e_bem(empresa_id)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
        ),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa_id,
            CadastrarBemIn(
                descricao="Computador",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("5000"),
                taxa_depreciacao_anual=Decimal("0.2000"),
                vida_util_meses=60,
            ),
        )

    chamada = bem_repo.criar.await_args
    # Taxa é re-derivada de 12/60 = 0.2000; vida permanece 60.
    assert chamada.kwargs["taxa_depreciacao_anual"] == Decimal("0.2000")
    assert chamada.kwargs["vida_util_meses"] == 60


@pytest.mark.asyncio
async def test_coerencia_taxa_20pct_vida_120_meses_rejeita() -> None:
    """taxa=20% + vida=120 meses → incoerentes (12/120=0.1 ≠ 0.2); deve rejeitar."""
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    empresa_repo, bem_repo = _mock_empresa_e_bem(empresa_id)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
        ),
        pytest.raises(LancamentoInvalido, match="162/1998"),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa_id,
            CadastrarBemIn(
                descricao="Computador",
                categoria=CategoriaBem.COMPUTADOR,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("5000"),
                taxa_depreciacao_anual=Decimal("0.2000"),
                vida_util_meses=120,
            ),
        )


@pytest.mark.asyncio
async def test_so_taxa_deriva_vida_util() -> None:
    """Só taxa=0.25 informada → vida_util derivada = round(12/0.25) = 48."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    empresa_repo, bem_repo = _mock_empresa_e_bem(empresa_id)
    tabela_repo = AsyncMock()
    # tabela não deve ser consultada
    tabela_repo.taxa_vigente = AsyncMock()

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.TabelaDepreciacaoRepo",
            return_value=tabela_repo,
        ),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
        ),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa_id,
            CadastrarBemIn(
                descricao="Veículo",
                categoria=CategoriaBem.VEICULO,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("80000"),
                taxa_depreciacao_anual=Decimal("0.25"),
            ),
        )

    tabela_repo.taxa_vigente.assert_not_called()
    chamada = bem_repo.criar.await_args
    assert chamada.kwargs["taxa_depreciacao_anual"] == Decimal("0.25")
    assert chamada.kwargs["vida_util_meses"] == 48  # round(12/0.25) = 48


@pytest.mark.asyncio
async def test_so_vida_util_deriva_taxa() -> None:
    """Só vida_util_meses=60 informada → taxa_anual derivada = 12/60 = 0.2000."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    empresa_repo, bem_repo = _mock_empresa_e_bem(empresa_id)
    tabela_repo = AsyncMock()
    tabela_repo.taxa_vigente = AsyncMock()

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.TabelaDepreciacaoRepo",
            return_value=tabela_repo,
        ),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
        ),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa_id,
            CadastrarBemIn(
                descricao="Máquina",
                categoria=CategoriaBem.MAQUINA,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("30000"),
                vida_util_meses=60,
            ),
        )

    tabela_repo.taxa_vigente.assert_not_called()
    chamada = bem_repo.criar.await_args
    assert chamada.kwargs["vida_util_meses"] == 60
    assert chamada.kwargs["taxa_depreciacao_anual"] == Decimal("0.2000")  # 12/60


@pytest.mark.asyncio
async def test_coerencia_com_arredondamento_aceita() -> None:
    """taxa=16.67% + vida=72 meses: taxa_esperada=12/72≈0.1667; diferença=0.0000→aceita."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    empresa_repo, bem_repo = _mock_empresa_e_bem(empresa_id)

    with (
        patch("app.modules.imobilizado.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.imobilizado.service.BemImobilizadoRepo", return_value=bem_repo
        ),
    ):
        await ImobilizadoService().cadastrar(
            session,
            uuid.uuid4(),
            empresa_id,
            CadastrarBemIn(
                descricao="Máquina industrial",
                categoria=CategoriaBem.MAQUINA,
                data_aquisicao=date(2026, 1, 1),
                valor_aquisicao=Decimal("50000"),
                # 12/72 = 0.16666... → arredondado 0.1667 — dentro da tolerância ±0.005
                taxa_depreciacao_anual=Decimal("0.1667"),
                vida_util_meses=72,
            ),
        )

    chamada = bem_repo.criar.await_args
    # Taxa é derivada de 12/72 = 0.1667 (quantizada em 4 casas)
    assert chamada.kwargs["vida_util_meses"] == 72
