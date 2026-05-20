"""Testes do plano referencial RFB (Sprint 9 PR1)."""

from __future__ import annotations

from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
    PLANO_REFERENCIAL,
)


class TestPlanoEstrutura:
    def test_tem_pelo_menos_30_contas(self) -> None:
        assert len(PLANO_REFERENCIAL) >= 30

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
        """Ativo/Despesa = D; Passivo/PL/Receita = C."""
        for item in PLANO_REFERENCIAL:
            if item.tipo in {"ativo", "despesa"}:
                # Exceção: depreciação acumulada é redutora de ativo (natureza C)
                if "Depreciação Acumulada" in item.descricao:
                    assert item.natureza == "C"
                else:
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
        for chave, codigo in CODIGOS_PADRAO_LANCAMENTO_AUTO.items():
            assert codigo in codigos, (
                f"chave {chave} → {codigo} não existe no plano"
            )

    def test_todos_mapeados_sao_analiticos(self) -> None:
        """O motor automático só pode lançar em contas analíticas."""
        analiticos = {
            item.codigo for item in PLANO_REFERENCIAL if item.aceita_lancamento
        }
        for chave, codigo in CODIGOS_PADRAO_LANCAMENTO_AUTO.items():
            assert codigo in analiticos, (
                f"{chave} → {codigo} não é analítica"
            )
