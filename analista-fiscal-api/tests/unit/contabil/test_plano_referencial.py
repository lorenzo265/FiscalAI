"""Testes do plano referencial RFB (Sprint 9 PR1).

Atualizado para cobrir as contas adicionadas na auditoria de completude
(impostos a recolher por tributo, PNC, deduções receita, resultado financeiro,
provisão IRPJ/CSLL, lucros distribuídos).
"""

from __future__ import annotations

import pytest

from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
    PLANO_REFERENCIAL,
    ItemPlano,
    codigo,
)

# Contas retificadoras (contranatureza intencional — não falhar a checagem geral).
# D em tipo receita: deduções da receita bruta (Lei 6.404/76 art. 187 I).
# D em tipo patrimonio_liquido: lucros distribuídos (redutora do PL).
# C em tipo ativo: depreciação acumulada (redutora do imobilizado).
_RETIFICADORAS_CODIGOS = {"4.1.03", "3.9.02", "1.2.3.99"}


class TestPlanoEstrutura:
    def test_tem_pelo_menos_30_contas(self) -> None:
        assert len(PLANO_REFERENCIAL) >= 30

    def test_contagem_golden(self) -> None:
        """Contagem exata após auditoria de completude — golden test."""
        # Baseline pré-auditoria: 47 contas.
        # Adicionadas: 6 impostos passivo (2.1.4.02-07) + 3 PNC (2.2, 2.2.1, 2.2.1.01)
        # + 1 lucros distribuídos (3.9.02) + 1 deduções receita (4.1.03)
        # + 1 receitas financeiras (4.9.01) + 4 financeiras/provisão (5.2, 5.2.01, 5.3, 5.3.01)
        # = 16 novas. Total = 63.
        assert len(PLANO_REFERENCIAL) == 63

    def test_5_grupos_raiz_presentes(self) -> None:
        codigos = {item.codigo for item in PLANO_REFERENCIAL}
        assert {"1", "2", "3", "4", "5"}.issubset(codigos)

    def test_todo_parent_codigo_existe(self) -> None:
        codigos = {item.codigo for item in PLANO_REFERENCIAL}
        for item in PLANO_REFERENCIAL:
            if item.parent_codigo is not None:
                assert item.parent_codigo in codigos, (
                    f"parent {item.parent_codigo} de {item.codigo} ausente"
                )

    def test_natureza_coerente_com_tipo(self) -> None:
        """Ativo/Despesa = D; Passivo/PL/Receita = C.

        Exceções registradas em _RETIFICADORAS_CODIGOS:
        - 1.2.3.99 Depreciação Acumulada: C em tipo ativo (redutora).
        - 4.1.03 Deduções da Receita Bruta: D em tipo receita (retificadora).
        - 3.9.02 Lucros Distribuídos: D em tipo patrimonio_liquido (redutora de PL).
        """
        for item in PLANO_REFERENCIAL:
            if item.codigo in _RETIFICADORAS_CODIGOS:
                continue  # contranatureza intencional — validado no golden abaixo
            if item.tipo in {"ativo", "despesa"}:
                assert item.natureza == "D", f"{item.codigo} deveria ser D"
            elif item.tipo in {"passivo", "patrimonio_liquido", "receita"}:
                assert item.natureza == "C", f"{item.codigo} deveria ser C"

    def test_nivel_coerente_com_profundidade_do_codigo(self) -> None:
        """Nível ≈ número de pontos no código + 1 (1.1.1 = nível 3)."""
        for item in PLANO_REFERENCIAL:
            pontos = item.codigo.count(".")
            assert item.nivel >= pontos + 1, (
                f"{item.codigo} nivel={item.nivel} pontos={pontos}"
            )

    def test_apenas_folhas_aceitam_lancamento(self) -> None:
        """Conta sintética (com filhos) não pode aceitar lançamento."""
        # Coleta códigos que têm filhos
        pais = {
            item.parent_codigo
            for item in PLANO_REFERENCIAL
            if item.parent_codigo is not None
        }
        for item in PLANO_REFERENCIAL:
            if item.codigo in pais:
                assert item.aceita_lancamento is False, (
                    f"{item.codigo} é pai mas aceita_lancamento=True"
                )

    def test_codigos_unicos(self) -> None:
        codigos = [item.codigo for item in PLANO_REFERENCIAL]
        assert len(codigos) == len(set(codigos))


class TestMapaCodigosPadrao:
    def test_todas_chaves_apontam_para_codigo_existente(self) -> None:
        codigos = {item.codigo for item in PLANO_REFERENCIAL}
        for chave, cod in CODIGOS_PADRAO_LANCAMENTO_AUTO.items():
            assert cod in codigos, (
                f"chave {chave} → {cod} não existe no plano"
            )

    def test_todos_mapeados_sao_analiticos(self) -> None:
        """O motor automático só pode lançar em contas analíticas."""
        analiticos = {
            item.codigo for item in PLANO_REFERENCIAL if item.aceita_lancamento
        }
        for chave, cod in CODIGOS_PADRAO_LANCAMENTO_AUTO.items():
            assert cod in analiticos, (
                f"{chave} → {cod} não é analítica"
            )


# ── Índice auxiliar para lookups nos golden tests ───────────────────────────
def _by_codigo(cod: str) -> ItemPlano:
    match = [i for i in PLANO_REFERENCIAL if i.codigo == cod]
    assert match, f"Conta {cod} não encontrada no plano"
    return match[0]


class TestContasNovas:
    """Golden tests para as contas adicionadas na auditoria de completude."""

    # ── 2.1.4.xx — Impostos a Recolher por tributo ──────────────────────────

    @pytest.mark.parametrize(
        "chave, cod, descricao",
        [
            ("icms_recolher", "2.1.4.02", "ICMS a Recolher"),
            ("iss_recolher", "2.1.4.03", "ISS a Recolher"),
            ("pis_recolher", "2.1.4.04", "PIS a Recolher"),
            ("cofins_recolher", "2.1.4.05", "COFINS a Recolher"),
            ("irpj_recolher", "2.1.4.06", "IRPJ a Recolher"),
            ("csll_recolher", "2.1.4.07", "CSLL a Recolher"),
        ],
    )
    def test_imposto_recolher(self, chave: str, cod: str, descricao: str) -> None:
        item = _by_codigo(cod)
        assert item.descricao == descricao
        assert item.natureza == "C"
        assert item.tipo == "passivo"
        assert item.parent_codigo == "2.1.4"
        assert item.aceita_lancamento is True
        assert item.nivel == 4
        # Chave simbólica resolve corretamente.
        assert codigo(chave) == cod

    # ── 2.2 — Passivo Não-Circulante ────────────────────────────────────────

    def test_pnc_grupo_sintetico(self) -> None:
        item = _by_codigo("2.2")
        assert item.descricao == "PASSIVO NÃO CIRCULANTE"
        assert item.natureza == "C"
        assert item.tipo == "passivo"
        assert item.parent_codigo == "2"
        assert item.aceita_lancamento is False
        assert item.nivel == 2

    def test_pnc_emprestimos_sintetico(self) -> None:
        item = _by_codigo("2.2.1")
        assert item.descricao == "Empréstimos e Financiamentos"
        assert item.parent_codigo == "2.2"
        assert item.aceita_lancamento is False
        assert item.nivel == 3

    def test_pnc_emprestimos_lp_analitico(self) -> None:
        item = _by_codigo("2.2.1.01")
        assert item.descricao == "Empréstimos e Financiamentos a Longo Prazo"
        assert item.natureza == "C"
        assert item.tipo == "passivo"
        assert item.parent_codigo == "2.2.1"
        assert item.aceita_lancamento is True
        assert item.nivel == 4
        assert codigo("emprestimos_lp") == "2.2.1.01"

    # ── 3.9.02 — Lucros Distribuídos ────────────────────────────────────────

    def test_lucros_distribuidos(self) -> None:
        item = _by_codigo("3.9.02")
        assert item.descricao == "Lucros Distribuídos"
        # Retificadora de PL: natureza D (reduz o patrimônio líquido)
        assert item.natureza == "D"
        assert item.tipo == "patrimonio_liquido"
        assert item.parent_codigo == "3.9"
        assert item.aceita_lancamento is True
        assert item.nivel == 3
        assert codigo("lucros_distribuidos") == "3.9.02"

    # ── 4.1.03 — Deduções da Receita Bruta ──────────────────────────────────

    def test_deducoes_receita_bruta(self) -> None:
        item = _by_codigo("4.1.03")
        assert item.descricao == "(-) Deduções da Receita Bruta"
        # Retificadora de receita: natureza D (devoluções/abatimentos reduzem ROB)
        assert item.natureza == "D"
        assert item.tipo == "receita"
        assert item.parent_codigo == "4.1"
        assert item.aceita_lancamento is True
        assert item.nivel == 3
        assert codigo("deducoes_receita") == "4.1.03"

    # ── 4.9.01 — Receitas Financeiras ───────────────────────────────────────

    def test_receitas_financeiras(self) -> None:
        item = _by_codigo("4.9.01")
        assert item.descricao == "Receitas Financeiras"
        assert item.natureza == "C"
        assert item.tipo == "receita"
        assert item.parent_codigo == "4.9"
        assert item.aceita_lancamento is True
        assert item.nivel == 3
        assert codigo("receitas_financeiras") == "4.9.01"

    # ── 5.2 — Despesas Financeiras ──────────────────────────────────────────

    def test_despesas_financeiras_grupo(self) -> None:
        item = _by_codigo("5.2")
        assert item.descricao == "Despesas Financeiras"
        assert item.natureza == "D"
        assert item.tipo == "despesa"
        assert item.parent_codigo == "5"
        assert item.aceita_lancamento is False
        assert item.nivel == 2

    def test_despesas_financeiras_analitico(self) -> None:
        item = _by_codigo("5.2.01")
        assert item.descricao == "Juros e Encargos Financeiros"
        assert item.natureza == "D"
        assert item.tipo == "despesa"
        assert item.parent_codigo == "5.2"
        assert item.aceita_lancamento is True
        assert item.nivel == 3
        assert codigo("despesas_financeiras") == "5.2.01"

    # ── 5.3 — Provisão IRPJ / CSLL ──────────────────────────────────────────

    def test_provisao_irpj_csll_grupo(self) -> None:
        item = _by_codigo("5.3")
        assert item.descricao == "Provisão para IRPJ e CSLL"
        assert item.natureza == "D"
        assert item.tipo == "despesa"
        assert item.parent_codigo == "5"
        assert item.aceita_lancamento is False
        assert item.nivel == 2

    def test_provisao_irpj_csll_analitico(self) -> None:
        item = _by_codigo("5.3.01")
        assert item.descricao == "Provisão IRPJ / CSLL do Exercício"
        assert item.natureza == "D"
        assert item.tipo == "despesa"
        assert item.parent_codigo == "5.3"
        assert item.aceita_lancamento is True
        assert item.nivel == 3
        assert codigo("provisao_irpj_csll") == "5.3.01"

    # ── Chaves simbólicas — resolução via codigo() ───────────────────────────

    def test_todas_chaves_novas_resolvem(self) -> None:
        """Todas as chaves novas devem resolver sem KeyError."""
        novas_chaves = [
            "icms_recolher",
            "iss_recolher",
            "pis_recolher",
            "cofins_recolher",
            "irpj_recolher",
            "csll_recolher",
            "emprestimos_lp",
            "lucros_distribuidos",
            "deducoes_receita",
            "receitas_financeiras",
            "despesas_financeiras",
            "provisao_irpj_csll",
        ]
        for chave in novas_chaves:
            resultado = codigo(chave)
            assert isinstance(resultado, str) and resultado, (
                f"codigo({chave!r}) retornou vazio"
            )

    def test_chave_inexistente_levanta_keyerror(self) -> None:
        with pytest.raises(KeyError):
            codigo("conta_que_nao_existe_jamais")
