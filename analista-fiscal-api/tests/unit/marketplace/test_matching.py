"""Golden tests do algoritmo de matching (Sprint 13 PR2)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.marketplace.matching import ALGORITMO_VERSAO, top_parceiros


@dataclass
class _FakeParceiro:
    id: UUID
    nome: str
    crc_numero: str = "100000"
    crc_uf: str = "SP"
    crc_status: str = "ativo"
    especialidades: list[str] | None = None
    uf_atuacao: list[str] | None = None
    rating_medio: Decimal | None = None
    total_consultas: int = 0
    taxa_resposta_horas: int | None = None
    sla_resposta_horas: int = 24
    oab_numero: str | None = None
    ativo: bool = True


def _p(
    nome: str,
    *,
    especialidades: list[str],
    rating: Decimal | None = None,
    consultas: int = 0,
    taxa: int | None = None,
    uf_atuacao: list[str] | None = None,
    ativo: bool = True,
    crc_status: str = "ativo",
    oab: str | None = None,
) -> _FakeParceiro:
    return _FakeParceiro(
        id=uuid4(),
        nome=nome,
        especialidades=list(especialidades),
        rating_medio=rating,
        total_consultas=consultas,
        taxa_resposta_horas=taxa,
        uf_atuacao=uf_atuacao,
        ativo=ativo,
        crc_status=crc_status,
        oab_numero=oab,
    )


def test_versao_estavel() -> None:
    assert ALGORITMO_VERSAO == "mkt-matching-2026.05"


def test_top_3_ordena_por_rating() -> None:
    parceiros = [
        _p("Joana 3.0", especialidades=["tributario"], rating=Decimal("3.0")),
        _p("Pedro 4.9", especialidades=["tributario"], rating=Decimal("4.9")),
        _p("Maria 4.2", especialidades=["tributario"], rating=Decimal("4.2")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf="SP", sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["Pedro 4.9", "Maria 4.2", "Joana 3.0"]


def test_empate_rating_desempata_por_consultas() -> None:
    parceiros = [
        _p("Veterano", especialidades=["tributario"], rating=Decimal("4.5"), consultas=50),
        _p("Novato", especialidades=["tributario"], rating=Decimal("4.5"), consultas=2),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["Veterano", "Novato"]


def test_empate_consultas_desempata_por_responsividade() -> None:
    parceiros = [
        _p("Lento", especialidades=["tributario"], rating=Decimal("4.5"), consultas=10, taxa=20),
        _p("Rapido", especialidades=["tributario"], rating=Decimal("4.5"), consultas=10, taxa=2),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["Rapido", "Lento"]


def test_rating_nulo_vai_para_o_fim() -> None:
    parceiros = [
        _p("Sem rating", especialidades=["tributario"], rating=None, consultas=100),
        _p("Com rating baixo", especialidades=["tributario"], rating=Decimal("1.5")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["Com rating baixo", "Sem rating"]


def test_filtra_sem_especialidade_requerida() -> None:
    # Categoria holding pede especialidade "societario"
    parceiros = [
        _p("Tributarista", especialidades=["tributario"], rating=Decimal("5.0")),
        _p("Societarista", especialidades=["societario"], rating=Decimal("3.0")),
    ]
    top = top_parceiros(parceiros, categoria="holding", uf=None, sla_aceitar_horas=48)
    assert [p.nome for p in top] == ["Societarista"]


def test_filtra_inativos_e_crc_suspenso() -> None:
    parceiros = [
        _p("Inativo", especialidades=["tributario"], ativo=False, rating=Decimal("5.0")),
        _p("CRC suspenso", especialidades=["tributario"], crc_status="suspenso", rating=Decimal("4.8")),
        _p("Valido", especialidades=["tributario"], rating=Decimal("3.0")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["Valido"]


def test_uf_atuacao_filtra_quando_cliente_tem_uf() -> None:
    parceiros = [
        _p("So_RJ", especialidades=["tributario"], uf_atuacao=["RJ"], rating=Decimal("5.0")),
        _p("Nacional", especialidades=["tributario"], uf_atuacao=None, rating=Decimal("3.0")),
        _p("Inclui_SP", especialidades=["tributario"], uf_atuacao=["SP", "RJ"], rating=Decimal("4.0")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf="SP", sla_aceitar_horas=4)
    nomes = [p.nome for p in top]
    assert "So_RJ" not in nomes
    assert nomes[0] == "Inclui_SP"  # rating 4 > nacional 3
    assert nomes[1] == "Nacional"


def test_uf_none_no_cliente_nao_filtra_por_uf() -> None:
    parceiros = [
        _p("So_RJ", especialidades=["tributario"], uf_atuacao=["RJ"], rating=Decimal("5.0")),
        _p("Nacional", especialidades=["tributario"], uf_atuacao=None, rating=Decimal("4.0")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=4)
    assert [p.nome for p in top] == ["So_RJ", "Nacional"]


def test_k_zero_retorna_lista_vazia() -> None:
    parceiros = [_p("Qualquer", especialidades=["tributario"], rating=Decimal("4.0"))]
    assert top_parceiros(parceiros, categoria="consulta_rapida", uf=None, k=0, sla_aceitar_horas=4) == []


def test_lista_vazia_retorna_vazia() -> None:
    assert top_parceiros([], categoria="consulta_rapida", uf="SP", sla_aceitar_horas=4) == []


def test_top_2_quando_pedimos_3_mas_so_2_elegiveis() -> None:
    parceiros = [
        _p("A", especialidades=["tributario"], rating=Decimal("4.0")),
        _p("B", especialidades=["tributario"], rating=Decimal("3.0")),
    ]
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, k=3, sla_aceitar_horas=4)
    assert len(top) == 2


def test_output_preserva_sla_aceitar_horas() -> None:
    parceiros = [_p("X", especialidades=["tributario"], rating=Decimal("4.0"))]
    top = top_parceiros(parceiros, categoria="holding", uf=None, sla_aceitar_horas=48)
    # holding tem especialidade societario, então X (tributario) filtrado
    # Vamos pedir consulta_rapida (tributario) com SLA custom
    top = top_parceiros(parceiros, categoria="consulta_rapida", uf=None, sla_aceitar_horas=99)
    assert top[0].sla_aceitar_horas == 99


def test_categoria_invalida_levanta() -> None:
    with pytest.raises(ValueError, match="Categoria desconhecida"):
        top_parceiros([], categoria="rebaba", uf=None, sla_aceitar_horas=1)
