"""Golden tests — Simples Nacional excluído de CBS/IBS na fase TESTE_2026.

Fundamento legal: LC 214/2025 art. 41-42 + Resolução CGSN.

Durante o período de teste 2026 (FaseReforma.TESTE_2026) as empresas
optantes pelo Simples Nacional e MEI NÃO apuram nem destacam CBS/IBS.
A exclusão cessa em 2027+ (FaseReforma.TRANSICAO / PLENO).

Casos cobertos:
  G1 — SN em 2026 → sem destaque CBS/IBS (valor 0 / calculou=False).
  G2 — Lucro Presumido em 2026 → destaque normal (0,9% / 0,1%).
  G3 — SN em 2027 → destaque presente (exclusão não se aplica em TRANSICAO).
  G4 — regime_excluido_fase_teste puro (unitário da função guard).
  G5 — backfill service: empresa SN 2026 → retorna imediatamente (0 docs).
  G6 — valor_total/valor_impostos nunca somam CBS/IBS (invariante §8.12).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.reforma.calcula_cbs_ibs import (
    ALGORITMO_VERSAO,
    AliquotaCBSIBS,
    regime_excluido_fase_teste,
)
from app.modules.reforma.integrar_documento import (
    popular_cbs_ibs_informacional,
)
from app.modules.reforma.periodo_transicao import FaseReforma
from app.modules.reforma.service import ReformaService


# ── fixtures ────────────────────────────────────────────────────────────────


def _aliquota_2026() -> AliquotaCBSIBS:
    """Vigência TESTE_2026: CBS 0,9% + IBS 0,1% (LC 214/2025 art. 348 §3º)."""
    return AliquotaCBSIBS(
        fase=FaseReforma.TESTE_2026,
        aliquota_cbs=Decimal("0.0090"),
        aliquota_ibs=Decimal("0.0010"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        fonte_norma="LC 214/2025 art. 348 §3º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


def _aliquota_2027() -> AliquotaCBSIBS:
    """Vigência TRANSICAO 2027: CBS plena 8,8% + IBS 0,1%."""
    return AliquotaCBSIBS(
        fase=FaseReforma.TRANSICAO,
        aliquota_cbs=Decimal("0.0880"),
        aliquota_ibs=Decimal("0.0010"),
        valid_from=date(2027, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 349",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


def _doc(
    *,
    valor_total: str = "1000.00",
    valor_cbs: str | None = None,
    valor_ibs: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        valor_total=Decimal(valor_total),
        valor_cbs=Decimal(valor_cbs) if valor_cbs is not None else None,
        valor_ibs=Decimal(valor_ibs) if valor_ibs is not None else None,
    )


def _empresa_sn(empresa_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=empresa_id or uuid.uuid4(),
        regime_tributario="simples_nacional",
        cnae_principal="47.30",
    )


def _empresa_lp(empresa_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=empresa_id or uuid.uuid4(),
        regime_tributario="lucro_presumido",
        cnae_principal="47.30",
    )


# ── G4: função guard pura ────────────────────────────────────────────────────


class TestRegimeExcluidoFaseTeste:
    """Unitários diretos sobre ``regime_excluido_fase_teste``."""

    def test_sn_teste_2026_excluido(self) -> None:
        assert regime_excluido_fase_teste("simples_nacional", FaseReforma.TESTE_2026) is True

    def test_mei_teste_2026_excluido(self) -> None:
        assert regime_excluido_fase_teste("mei", FaseReforma.TESTE_2026) is True

    def test_lucro_presumido_teste_2026_nao_excluido(self) -> None:
        assert regime_excluido_fase_teste("lucro_presumido", FaseReforma.TESTE_2026) is False

    def test_lucro_real_teste_2026_nao_excluido(self) -> None:
        assert regime_excluido_fase_teste("lucro_real", FaseReforma.TESTE_2026) is False

    def test_sn_transicao_2027_nao_excluido(self) -> None:
        # SN passa a destacar a partir de 2027
        assert regime_excluido_fase_teste("simples_nacional", FaseReforma.TRANSICAO) is False

    def test_sn_pleno_nao_excluido(self) -> None:
        assert regime_excluido_fase_teste("simples_nacional", FaseReforma.PLENO) is False

    def test_regime_none_nao_excluido(self) -> None:
        # Sem regime definido → sem exclusão (princípio do menor privilégio)
        assert regime_excluido_fase_teste(None, FaseReforma.TESTE_2026) is False


# ── G1: SN em 2026 → sem destaque ───────────────────────────────────────────


class TestSimlesNacional2026SemDestaque:
    """G1 — empresa SN em 2026 não recebe CBS/IBS informacional."""

    def test_sn_2026_calcula_false(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        assert r.calculou is False

    def test_sn_2026_valor_cbs_zero(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        assert r.valor_cbs == Decimal("0")

    def test_sn_2026_valor_ibs_zero(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        assert r.valor_ibs == Decimal("0")

    def test_sn_2026_observacao_menciona_lei(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        assert "LC 214/2025" in r.observacao
        assert "41-42" in r.observacao

    def test_sn_2026_algoritmo_versao_v2(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_mei_2026_tambem_excluido(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="5000.00"),
            _aliquota_2026(),
            regime_tributario="mei",
        )
        assert r.calculou is False
        assert r.valor_cbs == Decimal("0")
        assert r.valor_ibs == Decimal("0")


# ── G2: Lucro Presumido em 2026 → destaque normal ────────────────────────────


class TestLucroPresumido2026ComDestaque:
    """G2 — empresa Lucro Presumido em 2026 recebe destaque informacional normal."""

    def test_lp_2026_calcula_true(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="lucro_presumido",
        )
        assert r.calculou is True

    def test_lp_2026_valor_cbs_09_pct(self) -> None:
        # 1000,00 × 0,9% = 9,00
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="lucro_presumido",
        )
        assert r.valor_cbs == Decimal("9.00")

    def test_lp_2026_valor_ibs_01_pct(self) -> None:
        # 1000,00 × 0,1% = 1,00
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario="lucro_presumido",
        )
        assert r.valor_ibs == Decimal("1.00")

    def test_lucro_real_2026_tambem_calcula(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="2000.00"),
            _aliquota_2026(),
            regime_tributario="lucro_real",
        )
        assert r.calculou is True
        assert r.valor_cbs == Decimal("18.00")
        assert r.valor_ibs == Decimal("2.00")

    def test_regime_none_2026_calcula(self) -> None:
        """Regime desconhecido → sem exclusão → calcula normalmente."""
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2026(),
            regime_tributario=None,
        )
        assert r.calculou is True
        assert r.valor_cbs == Decimal("9.00")


# ── G3: SN em 2027 → destaque presente ──────────────────────────────────────


class TestSimlesNacional2027ComDestaque:
    """G3 — empresa SN em 2027 passa a destacar (exclusão não se aplica)."""

    def test_sn_2027_calcula_true(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2027(),
            regime_tributario="simples_nacional",
        )
        assert r.calculou is True

    def test_sn_2027_valor_cbs_positivo(self) -> None:
        # 1000,00 × 8,8% = 88,00
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2027(),
            regime_tributario="simples_nacional",
        )
        assert r.valor_cbs == Decimal("88.00")

    def test_sn_2027_valor_ibs_positivo(self) -> None:
        # 1000,00 × 0,1% = 1,00
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="1000.00"),
            _aliquota_2027(),
            regime_tributario="simples_nacional",
        )
        assert r.valor_ibs == Decimal("1.00")

    def test_mei_2027_tambem_calcula(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="500.00"),
            _aliquota_2027(),
            regime_tributario="mei",
        )
        assert r.calculou is True
        assert r.valor_cbs > Decimal("0")


# ── G6: invariante valor_total nunca soma CBS/IBS ────────────────────────────


class TestInvarianteValorTotal:
    """G6 — CBS/IBS são informacionais; valor_total do documento não muda.

    Princípio §8.12 — os campos valor_cbs/valor_ibs são anotativos; não
    são somados em valor_total nem em valor_impostos da nota.  Este teste
    confirma que a função helper não altera valor_total.
    """

    def test_valor_total_intocado_sn_2026(self) -> None:
        doc = _doc(valor_total="1000.00")
        resultado = popular_cbs_ibs_informacional(
            doc,
            _aliquota_2026(),
            regime_tributario="simples_nacional",
        )
        # base_calculo é preservado (doc.valor_total) mas não é alterado
        assert resultado.base_calculo == Decimal("1000.00")
        assert resultado.valor_cbs == Decimal("0")
        assert resultado.valor_ibs == Decimal("0")
        # doc.valor_total permanece intocado (helper não modifica o objeto)
        assert doc.valor_total == Decimal("1000.00")

    def test_valor_total_intocado_lp_2026(self) -> None:
        doc = _doc(valor_total="1000.00")
        resultado = popular_cbs_ibs_informacional(
            doc,
            _aliquota_2026(),
            regime_tributario="lucro_presumido",
        )
        assert resultado.base_calculo == Decimal("1000.00")
        assert doc.valor_total == Decimal("1000.00")
        # CBS+IBS são informacionais — NÃO somam no valor_total
        assert resultado.valor_cbs + resultado.valor_ibs == Decimal("10.00")
        # mas valor_total do doc permanece 1000,00 (não 1010,00)
        assert doc.valor_total == Decimal("1000.00")


# ── G5: backfill service — empresa SN 2026 retorna imediatamente ─────────────


class TestBackfillServiceSnExcluido:
    """G5 — recalcular_historico_documentos pula empresa SN em 2026."""

    @pytest.mark.asyncio
    async def test_sn_2026_retorna_zero_atualizados(self) -> None:
        empresa = _empresa_sn()
        session = AsyncMock()

        empresa_repo = AsyncMock()
        empresa_repo.por_id = AsyncMock(return_value=empresa)

        aliq_repo = AsyncMock()
        reforma_repo = AsyncMock()

        with (
            patch(
                "app.modules.reforma.service.EmpresaRepo",
                return_value=empresa_repo,
            ),
            patch(
                "app.modules.reforma.service.AliquotaCbsIbsRepo",
                return_value=aliq_repo,
            ),
            patch(
                "app.modules.reforma.service.ReformaRepo",
                return_value=reforma_repo,
            ),
        ):
            resultado = await ReformaService(session).recalcular_historico_documentos(
                empresa.id, ano=2026
            )

        assert resultado.atualizados == 0
        assert resultado.ignorados == 0
        # Não deve nem consultar alíquota nem buscar documentos
        aliq_repo.vigente.assert_not_awaited()
        reforma_repo.documentos_do_ano_sem_cbs.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sn_2027_processa_normalmente(self) -> None:
        """SN em 2027 não é interceptado pelo guard — backfill roda."""
        empresa = _empresa_sn()
        session = AsyncMock()

        doc = SimpleNamespace(
            id=uuid.uuid4(),
            valor_total=Decimal("1000.00"),
            valor_cbs=None,
            valor_ibs=None,
        )

        empresa_repo = AsyncMock()
        empresa_repo.por_id = AsyncMock(return_value=empresa)

        aliq_repo = AsyncMock()
        aliq_repo.vigente = AsyncMock(return_value=_aliquota_2027())

        reforma_repo = AsyncMock()
        reforma_repo.documentos_do_ano_sem_cbs = AsyncMock(return_value=[doc])
        reforma_repo.atualizar_cbs_ibs_documento = AsyncMock()

        with (
            patch(
                "app.modules.reforma.service.EmpresaRepo",
                return_value=empresa_repo,
            ),
            patch(
                "app.modules.reforma.service.AliquotaCbsIbsRepo",
                return_value=aliq_repo,
            ),
            patch(
                "app.modules.reforma.service.ReformaRepo",
                return_value=reforma_repo,
            ),
        ):
            resultado = await ReformaService(session).recalcular_historico_documentos(
                empresa.id, ano=2027
            )

        # SN em 2027 → calcula CBS/IBS → 1 documento atualizado
        assert resultado.atualizados == 1
        assert resultado.ignorados == 0
        aliq_repo.vigente.assert_awaited_once()
        reforma_repo.atualizar_cbs_ibs_documento.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lp_2026_processa_normalmente(self) -> None:
        """LP em 2026 não é interceptado — backfill roda normalmente."""
        empresa = _empresa_lp()
        session = AsyncMock()

        doc = SimpleNamespace(
            id=uuid.uuid4(),
            valor_total=Decimal("1000.00"),
            valor_cbs=None,
            valor_ibs=None,
        )

        empresa_repo = AsyncMock()
        empresa_repo.por_id = AsyncMock(return_value=empresa)

        aliq_repo = AsyncMock()
        aliq_repo.vigente = AsyncMock(return_value=_aliquota_2026())

        reforma_repo = AsyncMock()
        reforma_repo.documentos_do_ano_sem_cbs = AsyncMock(return_value=[doc])
        reforma_repo.atualizar_cbs_ibs_documento = AsyncMock()

        with (
            patch(
                "app.modules.reforma.service.EmpresaRepo",
                return_value=empresa_repo,
            ),
            patch(
                "app.modules.reforma.service.AliquotaCbsIbsRepo",
                return_value=aliq_repo,
            ),
            patch(
                "app.modules.reforma.service.ReformaRepo",
                return_value=reforma_repo,
            ),
        ):
            resultado = await ReformaService(session).recalcular_historico_documentos(
                empresa.id, ano=2026
            )

        assert resultado.atualizados == 1
        assert resultado.ignorados == 0
        reforma_repo.atualizar_cbs_ibs_documento.assert_awaited_once()
