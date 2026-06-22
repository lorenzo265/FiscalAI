"""Golden tests — calcula_checklist_lp.py (Sprint 20 PR2).

Princípio §8.4: golden tests bloqueiam merge.
Cada caso cobre: status de itens, contagens, percentual, status_geral.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.modules.lucro_presumido.calcula_checklist_lp import (
    ALGORITMO_VERSAO,
    ChecklistTrimestre,
    calcular_checklist_trimestre,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _apuracoes_t1_completas() -> frozenset[str]:
    """IRPJ + CSLL + PIS jan/fev/mar + Cofins jan/fev/mar para T1/2026."""
    return frozenset({
        "irpj:2026-01-01",
        "csll:2026-01-01",
        "pis:2026-01-01",
        "pis:2026-02-01",
        "pis:2026-03-01",
        "cofins:2026-01-01",
        "cofins:2026-02-01",
        "cofins:2026-03-01",
    })


def _darfs_t1_completos() -> frozenset[str]:
    """DARFs pagos: IRPJ(2089) + CSLL(2372) + PIS(8109)×3 + Cofins(2172)×3."""
    return frozenset({
        "2089:2026-01-01",
        "2372:2026-01-01",
        "8109:2026-01-01",
        "8109:2026-02-01",
        "8109:2026-03-01",
        "2172:2026-01-01",
        "2172:2026-02-01",
        "2172:2026-03-01",
    })


# ── Estrutura básica ──────────────────────────────────────────────────────────


def test_checklist_t1_retorna_checklisttrimestre() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert isinstance(r, ChecklistTrimestre)


def test_checklist_t1_total_itens_sem_apuracoes() -> None:
    """Sem apurações: 8 itens de apuração (2 trim + 3×2 mensais), 0 DARFs."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert r.total == 8


def test_checklist_t1_total_itens_com_todas_apuracoes() -> None:
    """Com todas apurações: 8 apurações + 8 DARFs = 16 itens."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=_apuracoes_t1_completas(),
        darfs_existentes=frozenset(),
    )
    assert r.total == 16


def test_checklist_ano_trimestre_gravados() -> None:
    r = calcular_checklist_trimestre(
        2026, 2,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert r.ano == 2026
    assert r.trimestre == 2


def test_checklist_algoritmo_versao() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert r.algoritmo_versao == ALGORITMO_VERSAO


# ── Status geral ──────────────────────────────────────────────────────────────


def test_status_geral_pendente_quando_nada_feito_e_nao_vencido() -> None:
    """Data futura, nenhuma apuração → 'pendente'."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 1, 15),  # no início do trimestre
    )
    assert r.status_geral == "pendente"


def test_status_geral_completo_quando_tudo_ok() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=_apuracoes_t1_completas(),
        darfs_existentes=_darfs_t1_completos(),
        data_referencia=date(2026, 5, 1),
    )
    assert r.status_geral == "completo"


def test_status_geral_parcial_quando_parte_ok_parte_pendente() -> None:
    """Só IRPJ apurado e pago, o resto pendente."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset({"2089:2026-01-01"}),
        data_referencia=date(2026, 2, 1),
    )
    assert r.status_geral == "parcial"


def test_status_geral_parcial_quando_tem_atrasado_e_ok() -> None:
    """Algum item 'ok', algum 'atrasado' → 'parcial'."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset({"2089:2026-01-01"}),
        data_referencia=date(2026, 6, 1),  # após vencimento de quase tudo
    )
    assert r.status_geral == "parcial"


# ── Contagens ─────────────────────────────────────────────────────────────────


def test_concluidos_zero_quando_nada_feito() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert r.concluidos == 0


def test_concluidos_igual_total_quando_tudo_ok() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=_apuracoes_t1_completas(),
        darfs_existentes=_darfs_t1_completos(),
    )
    assert r.concluidos == r.total


def test_pendentes_mais_atrasados_mais_concluidos_igual_total() -> None:
    """Invariante: pendentes + atrasados + concluidos == total."""
    r = calcular_checklist_trimestre(
        2026, 3,
        apuracoes_existentes=frozenset({"irpj:2026-07-01", "pis:2026-07-01"}),
        darfs_existentes=frozenset({"8109:2026-07-01"}),
        data_referencia=date(2026, 11, 1),
    )
    assert r.pendentes + r.atrasados + r.concluidos == r.total


def test_atrasados_quando_vencimento_passou() -> None:
    """Apurações não feitas e vencimento passou → atrasados."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 12, 1),  # tudo vencido
    )
    assert r.atrasados > 0
    assert r.pendentes == 0


# ── Percentual de conclusão ───────────────────────────────────────────────────


def test_percentual_zero_quando_nada_feito() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    assert r.percentual_conclusao == 0


def test_percentual_100_quando_tudo_ok() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=_apuracoes_t1_completas(),
        darfs_existentes=_darfs_t1_completos(),
    )
    assert r.percentual_conclusao == 100


def test_percentual_entre_0_e_100() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 3, 1),
    )
    assert 0 < r.percentual_conclusao < 100


# ── Status de itens individuais ───────────────────────────────────────────────


def test_item_irpj_ok_quando_apuracao_existe() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 2, 1),
    )
    irpj = next(i for i in r.itens if i.tipo == "apuracao_irpj")
    assert irpj.status == "ok"


def test_item_irpj_pendente_quando_nao_feito_e_nao_vencido() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 2, 1),
    )
    irpj = next(i for i in r.itens if i.tipo == "apuracao_irpj")
    assert irpj.status == "pendente"


def test_item_irpj_atrasado_quando_venceu() -> None:
    """IRPJ T1 vence 30/04/2026. Data 01/06/2026 → atrasado."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
        data_referencia=date(2026, 6, 1),
    )
    irpj = next(i for i in r.itens if i.tipo == "apuracao_irpj")
    assert irpj.status == "atrasado"


def test_item_darf_irpj_aparece_somente_se_apuracao_existe() -> None:
    """DARF só é gerado como item se a apuração foi realizada."""
    sem_apuracao = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    tipos = {i.tipo for i in sem_apuracao.itens}
    assert "darf_irpj" not in tipos

    com_apuracao = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset(),
    )
    tipos_com = {i.tipo for i in com_apuracao.itens}
    assert "darf_irpj" in tipos_com


def test_item_darf_irpj_ok_quando_darf_pago() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset({"2089:2026-01-01"}),
        data_referencia=date(2026, 4, 1),
    )
    darf = next(i for i in r.itens if i.tipo == "darf_irpj")
    assert darf.status == "ok"


def test_item_pis_mensal_por_mes() -> None:
    """PIS T1 gera 3 itens mensais (jan, fev, mar)."""
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    pis_items = [i for i in r.itens if i.tipo.startswith("apuracao_pis_")]
    assert len(pis_items) == 3
    meses = {i.competencia.month for i in pis_items}
    assert meses == {1, 2, 3}


def test_item_cofins_mensal_por_mes() -> None:
    """Cofins T2 gera 3 itens (abr, mai, jun)."""
    r = calcular_checklist_trimestre(
        2026, 2,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    cofins = [i for i in r.itens if i.tipo.startswith("apuracao_cofins_")]
    assert len(cofins) == 3
    meses = {i.competencia.month for i in cofins}
    assert meses == {4, 5, 6}


def test_descricao_irpj_contem_trimestre_e_ano() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    irpj = next(i for i in r.itens if i.tipo == "apuracao_irpj")
    assert "T1" in irpj.descricao
    assert "2026" in irpj.descricao


def test_descricao_pis_contem_nome_mes() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    pis_jan = next(i for i in r.itens if i.tipo == "apuracao_pis_01")
    assert "Janeiro" in pis_jan.descricao


# ── Trimestres ────────────────────────────────────────────────────────────────


def test_t4_meses_sao_out_nov_dez() -> None:
    r = calcular_checklist_trimestre(
        2026, 4,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    pis_items = [i for i in r.itens if i.tipo.startswith("apuracao_pis_")]
    meses = {i.competencia.month for i in pis_items}
    assert meses == {10, 11, 12}


def test_t4_irpj_competencia_outubro() -> None:
    r = calcular_checklist_trimestre(
        2026, 4,
        apuracoes_existentes=frozenset(),
        darfs_existentes=frozenset(),
    )
    irpj = next(i for i in r.itens if i.tipo == "apuracao_irpj")
    assert irpj.competencia == date(2026, 10, 1)


def test_trimestre_invalido_levanta_erro() -> None:
    with pytest.raises(ValueError, match="1, 2, 3 ou 4"):
        calcular_checklist_trimestre(
            2026, 5,
            apuracoes_existentes=frozenset(),
            darfs_existentes=frozenset(),
        )


def test_trimestre_zero_levanta_erro() -> None:
    with pytest.raises(ValueError, match="1, 2, 3 ou 4"):
        calcular_checklist_trimestre(
            2026, 0,
            apuracoes_existentes=frozenset(),
            darfs_existentes=frozenset(),
        )


# ── Propriedade completo ──────────────────────────────────────────────────────


def test_completo_true_quando_status_geral_completo() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=_apuracoes_t1_completas(),
        darfs_existentes=_darfs_t1_completos(),
    )
    assert r.completo is True


def test_completo_false_quando_parcial() -> None:
    r = calcular_checklist_trimestre(
        2026, 1,
        apuracoes_existentes=frozenset({"irpj:2026-01-01"}),
        darfs_existentes=frozenset(),
    )
    assert r.completo is False
