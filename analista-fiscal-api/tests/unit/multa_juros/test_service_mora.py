"""Testes unitários dos services de mora e denúncia espontânea."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.multa_juros.calcula_selic import ALGORITMO_VERSAO
from app.modules.multa_juros.schemas import SimularMoraIn


def _payload(
    valor: str = "1000.00",
    venc: str = "2025-01-01",
    pgto: str = "2025-04-15",
) -> SimularMoraIn:
    return SimularMoraIn(
        valor=Decimal(valor),
        data_vencimento=date.fromisoformat(venc),
        data_pagamento=date.fromisoformat(pgto),
    )


_TAXAS_MOCK = [(date(2025, m, 1), Decimal("0.0119")) for m in range(1, 13)]


# ── simular_mora ──────────────────────────────────────────────────────────────


async def test_simular_mora_retorna_com_multa() -> None:
    from app.modules.multa_juros.service import simular_mora

    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        out = await simular_mora(_payload(), session)

    assert out.multa_mora > Decimal("0")
    assert out.aliquota_multa == Decimal("0.20")   # 104 dias → teto


async def test_simular_mora_total_coerente() -> None:
    from app.modules.multa_juros.service import simular_mora

    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        out = await simular_mora(_payload(), session)

    assert out.total_acrescimos == out.multa_mora + out.juros_selic + out.acrescimo_mes_pagamento
    assert out.valor_atualizado == out.valor_original + out.total_acrescimos


# ── simular_denuncia_espontanea ───────────────────────────────────────────────


async def test_denuncia_espontanea_multa_zero() -> None:
    """CTN art. 138: multa_mora deve ser zero independente do prazo."""
    from app.modules.multa_juros.service import simular_denuncia_espontanea

    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        out = await simular_denuncia_espontanea(_payload(), session)

    assert out.multa_mora == Decimal("0")
    assert out.aliquota_multa == Decimal("0")


async def test_denuncia_espontanea_juros_iguais_mora() -> None:
    """SELIC e acréscimo mês devem ser idênticos em ambos os paths."""
    from app.modules.multa_juros.service import simular_denuncia_espontanea, simular_mora

    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        mora = await simular_mora(_payload(), session)
        espontanea = await simular_denuncia_espontanea(_payload(), session)

    assert espontanea.juros_selic == mora.juros_selic
    assert espontanea.acrescimo_mes_pagamento == mora.acrescimo_mes_pagamento
    assert espontanea.valor_atualizado < mora.valor_atualizado


async def test_denuncia_espontanea_sem_atraso_zero_tudo() -> None:
    from app.modules.multa_juros.service import simular_denuncia_espontanea

    payload = SimularMoraIn(
        valor=Decimal("500.00"),
        data_vencimento=date(2025, 5, 20),
        data_pagamento=date(2025, 5, 20),
    )
    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        out = await simular_denuncia_espontanea(payload, session)

    assert out.multa_mora == Decimal("0")
    assert out.juros_selic == Decimal("0")
    assert out.total_acrescimos == Decimal("0")
    assert out.valor_atualizado == Decimal("500.00")


# ── algoritmo_versao propagado ao SimularMoraOut ──────────────────────────────


async def test_simular_mora_propaga_algoritmo_versao() -> None:
    from app.modules.multa_juros.service import simular_mora

    session = AsyncMock()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ):
        out = await simular_mora(_payload(), session)

    assert out.algoritmo_versao == ALGORITMO_VERSAO


# ── extra="forbid" em SimularMoraIn ──────────────────────────────────────────


def test_simular_mora_in_rejeita_campo_extra() -> None:
    """SimularMoraIn com extra="forbid" deve rejeitar campos desconhecidos."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SimularMoraIn(
            valor=Decimal("100.00"),
            data_vencimento=date(2025, 1, 1),
            data_pagamento=date(2025, 4, 1),
            campo_invasor="oops",  # type: ignore[call-arg]
        )


# ── narrow except: ValueError não-SELIC não vira SelicInsuficienteError ──────


async def test_valor_error_nao_selic_nao_mascarado() -> None:
    """ValueError de 'pagamento anterior ao vencimento' não deve ser mascarado
    como SelicInsuficienteError — deve propagar como ValueError original."""
    from app.modules.multa_juros.service import simular_mora

    # Payload válido pelo schema (o model_validator aceita datas iguais).
    # Forcamos data_pagamento == data_vencimento → dias_atraso=0 → sem erro.
    # Para testar o except narrow, precisamos de um ValueError que NÃO seja de SELIC.
    # Criamos um mock que lança ValueError com mensagem diferente.
    session = AsyncMock()

    def _raise_non_selic(*args: object, **kwargs: object) -> object:
        raise ValueError("erro interno genérico — não é SELIC")

    payload = _payload()
    with patch(
        "app.modules.multa_juros.service.buscar_taxas_selic",
        new=AsyncMock(return_value=_TAXAS_MOCK),
    ), patch(
        "app.modules.multa_juros.service.calcular_mora",
        side_effect=_raise_non_selic,
    ):
        with pytest.raises(ValueError, match="erro interno genérico"):
            await simular_mora(payload, session)
