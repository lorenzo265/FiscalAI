"""FA4 — Higiene SCD CBS/IBS (M7): sem overlap, sem gap nas vigências.

Testa os invariantes SCD §8.3 das 3 fases da Reforma Tributária após a
migration 0054 fechar os ``valid_to`` anteriormente NULL.

Estratégia: testes puramente unitários que validam a lógica de intervalo
[valid_from, valid_to] das 3 linhas de seed sem precisar do banco.

Invariantes verificados:
  1. Para qualquer data de competência no cronograma (2026-01-01 … 2099-12-31),
     exatamente UMA vigência a cobre — sem overlap, sem gap.
  2. O mapeamento ``data → fase`` derivado de ``periodo_transicao.fase()`` é
     1:1 com o mapeamento ``data → vigência SCD`` — sem inconsistência.
  3. As 3 janelas de tempo não se sobrepõem.
  4. As janelas cobrem todo o período da Reforma sem buracos internos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator

import pytest

from app.modules.reforma.periodo_transicao import (
    FaseReforma,
    INICIO_PLENO,
    INICIO_TESTE_2026,
    INICIO_TRANSICAO,
    fase,
)


# ── Representação das vigências conforme seed 0034 + migration 0054 ──────────

@dataclass(frozen=True, slots=True)
class VigenciaScd:
    """Linha SCD de aliquota_cbs_ibs (campos relevantes para higiene)."""

    fase: FaseReforma
    valid_from: date
    valid_to: date | None  # None = vigência aberta (∞)

    def cobre(self, competencia: date) -> bool:
        """True se ``competencia`` cai dentro desta vigência [from, to]."""
        if competencia < self.valid_from:
            return False
        if self.valid_to is None:
            return True
        return competencia <= self.valid_to


# Seed pós-0054 — janelas fechadas (estado alvo após a migration FA4).
VIGENCIAS_POS_0054: list[VigenciaScd] = [
    VigenciaScd(
        fase=FaseReforma.TESTE_2026,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    ),
    VigenciaScd(
        fase=FaseReforma.TRANSICAO,
        valid_from=date(2027, 1, 1),
        valid_to=date(2032, 12, 31),
    ),
    VigenciaScd(
        fase=FaseReforma.PLENO,
        valid_from=date(2033, 1, 1),
        valid_to=None,  # vigência aberta corrente
    ),
]

# Seed pré-0054 — estado defeituoso (todos valid_to = NULL → overlap).
VIGENCIAS_PRE_0054: list[VigenciaScd] = [
    VigenciaScd(
        fase=FaseReforma.TESTE_2026,
        valid_from=date(2026, 1, 1),
        valid_to=None,  # BUG: deveria ser 2026-12-31
    ),
    VigenciaScd(
        fase=FaseReforma.TRANSICAO,
        valid_from=date(2027, 1, 1),
        valid_to=None,  # BUG: deveria ser 2032-12-31
    ),
    VigenciaScd(
        fase=FaseReforma.PLENO,
        valid_from=date(2033, 1, 1),
        valid_to=None,  # OK — vigência aberta corrente
    ),
]


def _vigencias_que_cobrem(
    vigencias: list[VigenciaScd], competencia: date
) -> list[VigenciaScd]:
    """Retorna quais vigências da lista cobrem ``competencia``."""
    return [v for v in vigencias if v.cobre(competencia)]


def _datas_representativas() -> Iterator[date]:
    """Gera datas representativas do cronograma da Reforma (2026–2099)."""
    marcos = [
        # Borda de início de cada fase
        date(2026, 1, 1),
        date(2026, 6, 15),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2028, 6, 1),
        date(2032, 12, 31),
        date(2033, 1, 1),
        date(2040, 5, 22),
        date(2099, 12, 31),
    ]
    yield from marcos


# ── Testes de higiene pós-migration 0054 ─────────────────────────────────────


class TestSeedPos0054SemOverlap:
    """Após migration 0054: nenhum par de vigências se sobrepõe no tempo."""

    def test_vigencias_nao_se_sobrepoem(self) -> None:
        """Para todo par (i, j) i≠j, não existe data coberta por ambos."""
        vs = VIGENCIAS_POS_0054
        for i, vi in enumerate(vs):
            for j, vj in enumerate(vs):
                if i >= j:
                    continue
                # Verificar por amostragem densa: início e fim de cada fase.
                datas_de_borda = [vi.valid_from, vj.valid_from]
                if vi.valid_to:
                    datas_de_borda.append(vi.valid_to)
                if vj.valid_to:
                    datas_de_borda.append(vj.valid_to)

                for d in datas_de_borda:
                    coberturas = [v.cobre(d) for v in [vi, vj]]
                    assert coberturas.count(True) <= 1, (
                        f"Overlap detectado em {d}: "
                        f"{vi.fase.value} e {vj.fase.value} cobrem a mesma data."
                    )

    @pytest.mark.parametrize("competencia", list(_datas_representativas()))
    def test_exatamente_uma_vigencia_por_data(self, competencia: date) -> None:
        """Exatamente 1 vigência cobre cada data do cronograma (sem overlap)."""
        cobrindo = _vigencias_que_cobrem(VIGENCIAS_POS_0054, competencia)
        assert len(cobrindo) == 1, (
            f"Esperado 1 vigência cobrindo {competencia}, "
            f"encontrado {len(cobrindo)}: {[v.fase.value for v in cobrindo]}"
        )


class TestSeedPos0054SemGap:
    """Após migration 0054: cobertura contínua de 2026-01-01 até ∞."""

    def test_sem_gap_entre_teste_e_transicao(self) -> None:
        """2026-12-31 (último dia do teste) é coberto; 2027-01-01 também."""
        ultimo_teste = date(2026, 12, 31)
        primeiro_transicao = date(2027, 1, 1)

        cobrem_ultimo_teste = _vigencias_que_cobrem(VIGENCIAS_POS_0054, ultimo_teste)
        cobrem_primeiro_transicao = _vigencias_que_cobrem(
            VIGENCIAS_POS_0054, primeiro_transicao
        )

        assert len(cobrem_ultimo_teste) == 1
        assert cobrem_ultimo_teste[0].fase is FaseReforma.TESTE_2026

        assert len(cobrem_primeiro_transicao) == 1
        assert cobrem_primeiro_transicao[0].fase is FaseReforma.TRANSICAO

    def test_sem_gap_entre_transicao_e_pleno(self) -> None:
        """2032-12-31 (último dia da transição) é coberto; 2033-01-01 também."""
        ultimo_transicao = date(2032, 12, 31)
        primeiro_pleno = date(2033, 1, 1)

        cobrem_ultimo = _vigencias_que_cobrem(VIGENCIAS_POS_0054, ultimo_transicao)
        cobrem_primeiro = _vigencias_que_cobrem(VIGENCIAS_POS_0054, primeiro_pleno)

        assert len(cobrem_ultimo) == 1
        assert cobrem_ultimo[0].fase is FaseReforma.TRANSICAO

        assert len(cobrem_primeiro) == 1
        assert cobrem_primeiro[0].fase is FaseReforma.PLENO

    def test_pleno_cobre_datas_futuras(self) -> None:
        """Regime pleno (valid_to=None) cobre qualquer data >= 2033-01-01."""
        datas_futuras = [
            date(2033, 1, 1),
            date(2040, 1, 1),
            date(2099, 12, 31),
        ]
        for d in datas_futuras:
            cobrindo = _vigencias_que_cobrem(VIGENCIAS_POS_0054, d)
            assert len(cobrindo) == 1
            assert cobrindo[0].fase is FaseReforma.PLENO, (
                f"Esperado PLENO cobrindo {d}, mas {cobrindo[0].fase.value}"
            )


class TestJanelasExplicitasPeriodoTransicao:
    """valid_from/valid_to das vigências SCD batem com os marcos de periodo_transicao."""

    def test_valid_from_bate_com_inicio_fase(self) -> None:
        """O valid_from de cada vigência SCD == constante INICIO_* do módulo."""
        vs = VIGENCIAS_POS_0054
        assert vs[0].valid_from == INICIO_TESTE_2026
        assert vs[1].valid_from == INICIO_TRANSICAO
        assert vs[2].valid_from == INICIO_PLENO

    def test_valid_to_bate_com_um_dia_antes_da_proxima_fase(self) -> None:
        """valid_to da fase N == INICIO da fase N+1 menos um dia."""
        vs = VIGENCIAS_POS_0054
        assert vs[0].valid_to == INICIO_TRANSICAO - timedelta(days=1)
        assert vs[1].valid_to == INICIO_PLENO - timedelta(days=1)
        assert vs[2].valid_to is None  # regime pleno = vigência aberta

    @pytest.mark.parametrize("competencia", list(_datas_representativas()))
    def test_mapeamento_fase_consistente_com_scd(
        self, competencia: date
    ) -> None:
        """``periodo_transicao.fase(d)`` e lookup SCD produzem a mesma fase."""
        fase_func = fase(competencia)
        cobrindo = _vigencias_que_cobrem(VIGENCIAS_POS_0054, competencia)
        assert len(cobrindo) == 1
        fase_scd = cobrindo[0].fase
        assert fase_func is fase_scd, (
            f"Inconsistência em {competencia}: "
            f"periodo_transicao.fase()={fase_func.value}, "
            f"SCD={fase_scd.value}"
        )


# ── Teste de regressão: seed PRÉ-0054 TEM overlap (valida o defeito M7) ──────


class TestSeedPre0054TemOverlap:
    """Documenta e prova o defeito M7: seed original tem overlap.

    Este teste VERIFICA que o defeito existia — se o defeito fosse corrigido
    no seed 0034 (o que não foi), este teste falharia e precisaria ser removido.
    Serve como especificação do problema que a migration 0054 resolve.
    """

    @pytest.mark.parametrize(
        "competencia",
        [
            date(2027, 1, 1),  # cobre tanto teste_2026 (NULL) quanto transicao
            date(2032, 12, 31),  # cobre transicao E pleno (ambos NULL)
            date(2033, 1, 1),  # cobre todos os 3 (todos NULL no pre-0054)
        ],
    )
    def test_pre_0054_tem_multiplas_vigencias_por_data(
        self, competencia: date
    ) -> None:
        """Antes da 0054: 2+ vigências cobrem a mesma data (overlap bug M7)."""
        cobrindo = _vigencias_que_cobrem(VIGENCIAS_PRE_0054, competencia)
        assert len(cobrindo) > 1, (
            f"Esperado overlap (>1 vigência) em {competencia} para o seed "
            f"pré-0054, mas apenas {len(cobrindo)} vigência(s) encontrada(s). "
            f"O defeito M7 pode ter sido corrigido na fonte?"
        )
