"""Testes dos validadores §8.6 puros (Sprint 19.5 PR1).

Cada teste exercita uma regra específica isoladamente — golden por regra
(§8.4 do PlanoBackend). Re-uso o builder ``vigencia_*_valida`` e
sobrescrevo apenas o campo que quero invalidar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.tabelas_admin.salario_minimo import salario_minimo_oficial
from app.modules.tabelas_admin.schemas import (
    AliquotaCbsIbsIn,
    AliquotaFgtsIn,
    AliquotaIcmsUfIn,
    FaixaInssIn,
    FaixaIrrfIn,
    PresuncaoLpIn,
)
from app.modules.tabelas_admin.validadores import (
    validar_vigencia_cbs_ibs,
    validar_vigencia_fgts,
    validar_vigencia_icms_uf,
    validar_vigencia_inss,
    validar_vigencia_irrf,
    validar_vigencia_presuncao_lp,
    validar_vigencia_simples_nacional,
)
from app.shared.exceptions import VigenciaTributariaInvalida
from tests.unit.tabelas_admin._helpers import (
    faixas_inss_2026,
    faixas_irrf_2026,
    faixas_simples_anexo_iii,
    vigencia_cbs_ibs_valida,
    vigencia_fgts_valida,
    vigencia_icms_uf_valida,
    vigencia_inss_valida,
    vigencia_irrf_valida,
    vigencia_presuncao_valida,
    vigencia_simples_valida,
)

# ── INSS ────────────────────────────────────────────────────────────────────


def test_inss_payload_canonico_passa() -> None:
    validar_vigencia_inss(vigencia_inss_valida())


def test_inss_faixas_nao_progressivas_falha() -> None:
    faixas = faixas_inss_2026()
    # Faixa 2 com valor_ate menor que faixa 1 → quebra progressão.
    faixas[1] = FaixaInssIn(
        tipo="empregado",
        faixa=2,
        valor_ate=Decimal("1000.00"),  # < 1620 da faixa 1
        aliquota=Decimal("0.09"),
    )
    with pytest.raises(VigenciaTributariaInvalida, match="progressivas"):
        validar_vigencia_inss(vigencia_inss_valida(faixas=faixas))


def test_inss_aliquota_implausivel_falha() -> None:
    """Alíquota 0.75 (75%) — defesa anti-typo (esperado 0.075)."""
    faixas = faixas_inss_2026()
    faixas[0] = FaixaInssIn(
        tipo="empregado",
        faixa=1,
        valor_ate=Decimal("1620.00"),
        aliquota=Decimal("0.75"),
    )
    with pytest.raises(VigenciaTributariaInvalida, match="plausível"):
        validar_vigencia_inss(vigencia_inss_valida(faixas=faixas))


def test_inss_primeira_faixa_abaixo_salario_minimo_falha() -> None:
    """Primeira faixa precisa cobrir 1 salário mínimo (R$ 1.621,00 em 2026)."""
    faixas = faixas_inss_2026()
    faixas[0] = FaixaInssIn(
        tipo="empregado",
        faixa=1,
        valor_ate=Decimal("1000.00"),  # < SM 2026
        aliquota=Decimal("0.075"),
    )
    # Os outros valor_ate continuam > 1000, então a progressão ainda é OK.
    with pytest.raises(VigenciaTributariaInvalida, match="salário mínimo"):
        validar_vigencia_inss(vigencia_inss_valida(faixas=faixas))


def test_inss_sem_faixa_empregado_falha() -> None:
    """Tabela INSS sem faixa empregado é inválida (folha CLT precisa)."""
    apenas_ci = [
        FaixaInssIn(
            tipo="contribuinte_individual",
            faixa=1,
            valor_ate=Decimal("8530.06"),
            aliquota=Decimal("0.11"),
        )
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="empregado"):
        validar_vigencia_inss(vigencia_inss_valida(faixas=apenas_ci))


def test_inss_faixa_empregado_gap_falha() -> None:
    """Faixas empregado 1, 2, 4 (sem 3) deve falhar."""
    faixas = [
        f for f in faixas_inss_2026() if not (f.tipo == "empregado" and f.faixa == 3)
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="sequencial"):
        validar_vigencia_inss(vigencia_inss_valida(faixas=faixas))


def test_inss_ano_sem_salario_minimo_cadastrado_falha() -> None:
    """Ano 2099 não está no dict → mensagem explicativa para atualizar."""
    with pytest.raises(VigenciaTributariaInvalida, match="(?i)salário mínimo"):
        validar_vigencia_inss(vigencia_inss_valida(valid_from=date(2099, 1, 1)))


# ── IRRF ────────────────────────────────────────────────────────────────────


def test_irrf_payload_canonico_passa() -> None:
    validar_vigencia_irrf(vigencia_irrf_valida())


def test_irrf_faixa_isencao_com_aliquota_diferente_de_zero_falha() -> None:
    faixas = faixas_irrf_2026()
    faixas[0] = FaixaIrrfIn(
        faixa=1,
        base_ate=Decimal("2428.80"),
        aliquota=Decimal("0.075"),  # Faixa 1 deveria ser 0
        parcela_deduzir=Decimal("0"),
    )
    with pytest.raises(VigenciaTributariaInvalida, match="isenção"):
        validar_vigencia_irrf(vigencia_irrf_valida(faixas=faixas))


def test_irrf_primeira_faixa_abaixo_salario_minimo_falha() -> None:
    faixas = faixas_irrf_2026()
    faixas[0] = FaixaIrrfIn(
        faixa=1,
        base_ate=Decimal("1000.00"),  # < SM 2026
        aliquota=Decimal("0"),
        parcela_deduzir=Decimal("0"),
    )
    with pytest.raises(VigenciaTributariaInvalida, match="salário mínimo"):
        validar_vigencia_irrf(vigencia_irrf_valida(faixas=faixas))


def test_irrf_aliquotas_nao_progressivas_falha() -> None:
    """Faixa 4 (22,5%) maior que faixa 3 (15%) é OK; aqui invertemos a 4 e 3."""
    faixas = faixas_irrf_2026()
    faixas[2] = FaixaIrrfIn(
        faixa=3,
        base_ate=Decimal("3751.05"),
        aliquota=Decimal("0.25"),  # > faixa 4 (0.225) → quebra progressão
        parcela_deduzir=Decimal("394.16"),
    )
    with pytest.raises(VigenciaTributariaInvalida, match="progressivas"):
        validar_vigencia_irrf(vigencia_irrf_valida(faixas=faixas))


# ── FGTS ────────────────────────────────────────────────────────────────────


def test_fgts_payload_canonico_passa() -> None:
    validar_vigencia_fgts(vigencia_fgts_valida())


def test_fgts_vinculo_repetido_falha() -> None:
    aliquotas = [
        AliquotaFgtsIn(vinculo="clt", aliquota=Decimal("0.08")),
        AliquotaFgtsIn(vinculo="clt", aliquota=Decimal("0.08")),  # duplicado
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="mais de uma vez"):
        validar_vigencia_fgts(vigencia_fgts_valida(aliquotas=aliquotas))


def test_fgts_aliquota_implausivel_falha() -> None:
    aliquotas = [AliquotaFgtsIn(vinculo="clt", aliquota=Decimal("0.50"))]
    with pytest.raises(VigenciaTributariaInvalida, match="plausível"):
        validar_vigencia_fgts(vigencia_fgts_valida(aliquotas=aliquotas))


# ── Simples Nacional ────────────────────────────────────────────────────────


def test_simples_nacional_payload_canonico_passa() -> None:
    validar_vigencia_simples_nacional(vigencia_simples_valida())


def test_simples_faixas_progressivas_quebradas_falha() -> None:
    faixas = faixas_simples_anexo_iii()
    faixas[1] = faixas[1].model_copy(
        update={"rbt12_ate": Decimal("100000.00")}  # < faixa 1 (180k)
    )
    with pytest.raises(VigenciaTributariaInvalida, match="progressivas"):
        validar_vigencia_simples_nacional(
            vigencia_simples_valida(faixas=faixas)
        )


def test_simples_teto_baixo_demais_falha() -> None:
    """Faixa 6 cobrindo só R$ 2MM dispara aviso (esperado ~R$ 4,8MM).

    Preciso manter progressão entre as 6 faixas e cair só na heurística do
    teto — então recomprimo todas as faixas em escala 1:1.
    """
    from app.modules.tabelas_admin.schemas import FaixaSimplesIn

    faixas = [
        FaixaSimplesIn(
            faixa=1, rbt12_ate=Decimal("100000.00"),
            aliquota_nominal=Decimal("0.06"), parcela_deduzir=Decimal("0"),
        ),
        FaixaSimplesIn(
            faixa=2, rbt12_ate=Decimal("200000.00"),
            aliquota_nominal=Decimal("0.10"), parcela_deduzir=Decimal("100"),
        ),
        FaixaSimplesIn(
            faixa=3, rbt12_ate=Decimal("500000.00"),
            aliquota_nominal=Decimal("0.13"), parcela_deduzir=Decimal("200"),
        ),
        FaixaSimplesIn(
            faixa=4, rbt12_ate=Decimal("1000000.00"),
            aliquota_nominal=Decimal("0.16"), parcela_deduzir=Decimal("300"),
        ),
        FaixaSimplesIn(
            faixa=5, rbt12_ate=Decimal("1500000.00"),
            aliquota_nominal=Decimal("0.20"), parcela_deduzir=Decimal("400"),
        ),
        FaixaSimplesIn(
            faixa=6, rbt12_ate=Decimal("2000000.00"),  # < 3MM heurístico
            aliquota_nominal=Decimal("0.25"), parcela_deduzir=Decimal("500"),
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="4.800.000"):
        validar_vigencia_simples_nacional(
            vigencia_simples_valida(faixas=faixas)
        )


# ── Presunção LP ────────────────────────────────────────────────────────────


def test_presuncao_lp_payload_canonico_passa() -> None:
    validar_vigencia_presuncao_lp(vigencia_presuncao_valida())


def test_presuncao_irpj_implausivel_falha() -> None:
    presuncoes = [
        PresuncaoLpIn(
            grupo_atividade="Comércio em geral",
            cnae_pattern="47",
            percentual_irpj=Decimal("0.50"),  # acima do plausível
            percentual_csll=Decimal("0.12"),
            prioridade=10,
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="IRPJ"):
        validar_vigencia_presuncao_lp(
            vigencia_presuncao_valida(presuncoes=presuncoes)
        )


# ── ICMS UF ─────────────────────────────────────────────────────────────────


def test_icms_uf_payload_canonico_passa() -> None:
    validar_vigencia_icms_uf(vigencia_icms_uf_valida())


def test_icms_uf_invalida_falha() -> None:
    aliquotas = [
        AliquotaIcmsUfIn(
            uf="XX",
            aliquota_interna=Decimal("0.18"),
            aliquota_fecp=Decimal("0"),
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="27 UFs"):
        validar_vigencia_icms_uf(vigencia_icms_uf_valida(aliquotas=aliquotas))


def test_icms_uf_duplicada_falha() -> None:
    aliquotas = [
        AliquotaIcmsUfIn(
            uf="SP",
            aliquota_interna=Decimal("0.18"),
            aliquota_fecp=Decimal("0"),
        ),
        AliquotaIcmsUfIn(
            uf="SP",  # duplicado
            aliquota_interna=Decimal("0.18"),
            aliquota_fecp=Decimal("0"),
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="mais de uma vez"):
        validar_vigencia_icms_uf(vigencia_icms_uf_valida(aliquotas=aliquotas))


# ── CBS / IBS ───────────────────────────────────────────────────────────────


def test_cbs_ibs_payload_canonico_passa() -> None:
    validar_vigencia_cbs_ibs(vigencia_cbs_ibs_valida())


def test_cbs_ibs_fase_desconhecida_falha() -> None:
    aliquotas = [
        AliquotaCbsIbsIn(
            fase="fase_inventada",
            regime=None,
            cnae_pattern=None,
            classificacao_lc214="geral",
            aliquota_cbs=Decimal("0.09"),
            aliquota_ibs=Decimal("0.18"),
            observacao=None,
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="LC 214"):
        validar_vigencia_cbs_ibs(vigencia_cbs_ibs_valida(aliquotas=aliquotas))


def test_cbs_ibs_aliquota_acima_do_maximo_falha() -> None:
    aliquotas = [
        AliquotaCbsIbsIn(
            fase="teste_2026",
            regime=None,
            cnae_pattern=None,
            classificacao_lc214="geral",
            aliquota_cbs=Decimal("0.50"),  # > 0.30 do limite plausível
            aliquota_ibs=Decimal("0.001"),
            observacao=None,
        ),
    ]
    with pytest.raises(VigenciaTributariaInvalida, match="CBS"):
        validar_vigencia_cbs_ibs(vigencia_cbs_ibs_valida(aliquotas=aliquotas))


# ── Salário mínimo (helper isolado) ─────────────────────────────────────────


def test_salario_minimo_2025_conhecido() -> None:
    assert salario_minimo_oficial(2025) == Decimal("1518.00")


def test_salario_minimo_ano_nao_cadastrado_levanta_valueerror() -> None:
    with pytest.raises(ValueError, match="2099"):
        salario_minimo_oficial(2099)
