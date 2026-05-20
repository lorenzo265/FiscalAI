"""Golden tests da validação de partidas dobradas (Sprint 9 PR1)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.modules.contabil.partidas import (
    ALGORITMO_VERSAO,
    ContaView,
    PartidaIn,
    validar_partidas,
)


def _conta(
    aceita: bool = True,
    empresa_id: uuid.UUID | None = None,
    valid_from: date = date(2025, 1, 1),
    valid_to: date | None = None,
) -> ContaView:
    return ContaView(
        id=uuid.uuid4(),
        empresa_id=empresa_id or uuid.uuid4(),
        aceita_lancamento=aceita,
        valid_from=valid_from,
        valid_to=valid_to,
    )


class TestPartidasDobradas:
    def test_balanceado_valor_igual_passa(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("100")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("100")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert r.valido is True
        assert r.erros == ()
        assert r.total_debito == Decimal("100")
        assert r.total_credito == Decimal("100")
        assert r.versao == ALGORITMO_VERSAO

    def test_desbalanceado_falha(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("100")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("90")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert r.valido is False
        assert any("desbalanceadas" in e for e in r.erros)

    def test_3_partidas_2D_1C_balanceado(self) -> None:
        eid = uuid.uuid4()
        c1, c2, c3 = _conta(empresa_id=eid), _conta(empresa_id=eid), _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("60")),
            PartidaIn(conta_id=c2.id, tipo="D", valor=Decimal("40")),
            PartidaIn(conta_id=c3.id, tipo="C", valor=Decimal("100")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2, c3.id: c3},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert r.valido is True

    def test_apenas_uma_partida_falha(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        partidas = [PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("100"))]
        r = validar_partidas(
            partidas, {c1.id: c1},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert "min_2_partidas" in r.erros


class TestContaAnalitica:
    def test_conta_sintetica_recusada(self) -> None:
        eid = uuid.uuid4()
        sintetica = _conta(aceita=False, empresa_id=eid)
        analitica = _conta(aceita=True, empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=sintetica.id, tipo="D", valor=Decimal("50")),
            PartidaIn(conta_id=analitica.id, tipo="C", valor=Decimal("50")),
        ]
        r = validar_partidas(
            partidas, {sintetica.id: sintetica, analitica.id: analitica},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert r.valido is False
        assert any("sintetica" in e for e in r.erros)


class TestEmpresa:
    def test_conta_de_outra_empresa_recusada(self) -> None:
        empresa_a = uuid.uuid4()
        empresa_b = uuid.uuid4()
        c_b = _conta(empresa_id=empresa_b)
        c_a = _conta(empresa_id=empresa_a)
        partidas = [
            PartidaIn(conta_id=c_b.id, tipo="D", valor=Decimal("10")),
            PartidaIn(conta_id=c_a.id, tipo="C", valor=Decimal("10")),
        ]
        r = validar_partidas(
            partidas, {c_b.id: c_b, c_a.id: c_a},
            empresa_id=empresa_a, competencia=date(2026, 5, 1),
        )
        assert r.valido is False
        assert any("outra_empresa" in e for e in r.erros)

    def test_conta_nao_encontrada_no_lookup(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        id_fantasma = uuid.uuid4()
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("10")),
            PartidaIn(conta_id=id_fantasma, tipo="C", valor=Decimal("10")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert any("nao_encontrada" in e for e in r.erros)


class TestVigencia:
    def test_competencia_antes_de_valid_from_falha(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid, valid_from=date(2026, 6, 1))
        c2 = _conta(empresa_id=eid, valid_from=date(2026, 6, 1))
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("10")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("10")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert r.valido is False
        assert any("fora_vigencia" in e for e in r.erros)

    def test_competencia_depois_de_valid_to_falha(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(
            empresa_id=eid,
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("10")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("10")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert any("fora_vigencia" in e for e in r.erros)


class TestValorPositivo:
    def test_valor_zero_recusado(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="D", valor=Decimal("0")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("0")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert any("nao_positivo" in e for e in r.erros)


class TestTipoInvalido:
    def test_tipo_diferente_de_dc_recusado(self) -> None:
        eid = uuid.uuid4()
        c1 = _conta(empresa_id=eid)
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=c1.id, tipo="X", valor=Decimal("10")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("10")),
        ]
        r = validar_partidas(
            partidas, {c1.id: c1, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        assert any("tipo_invalido" in e for e in r.erros)


class TestAcumulacaoDeErros:
    def test_multiplos_erros_acumulados(self) -> None:
        """Validador deve devolver TODOS os erros, não parar no primeiro."""
        eid = uuid.uuid4()
        sintetica = _conta(aceita=False, empresa_id=eid)
        c2 = _conta(empresa_id=eid)
        partidas = [
            PartidaIn(conta_id=sintetica.id, tipo="D", valor=Decimal("100")),
            PartidaIn(conta_id=c2.id, tipo="C", valor=Decimal("50")),
        ]
        r = validar_partidas(
            partidas, {sintetica.id: sintetica, c2.id: c2},
            empresa_id=eid, competencia=date(2026, 5, 1),
        )
        # Deve ter pelo menos: conta_sintetica + desbalanceadas
        assert len(r.erros) >= 2
        assert any("sintetica" in e for e in r.erros)
        assert any("desbalanceadas" in e for e in r.erros)
