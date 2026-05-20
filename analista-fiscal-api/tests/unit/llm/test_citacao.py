"""Testes unitários das funções puras de validação de citação."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.shared.llm.citacao import (
    RESPOSTA_PADRAO_VERIFICAR,
    detectar_out_of_scope,
    extrair_cnpjs,
    extrair_datas,
    extrair_valores_monetarios,
    validar_resposta,
)
from app.shared.llm.client import Citacao, FonteFato, LLMProvider, LLMResponse


def _resp(texto: str, citacoes: list[Citacao] | None = None) -> LLMResponse:
    return LLMResponse(
        texto=texto,
        citacoes=citacoes or [],
        tokens_input=0,
        tokens_output=0,
        tokens_cached=0,
        custo_usd=Decimal("0"),
        provider=LLMProvider.GEMINI_2_5_FLASH_LITE,
        latencia_ms=0,
    )


def _fonte(id_: str, payload: str, tipo: str = "apuracao_das") -> FonteFato:
    return FonteFato(id=id_, tipo=tipo, payload=payload)


# ── extrair_valores_monetarios ───────────────────────────────────────────────


def test_extrai_valor_simples() -> None:
    assert "R$ 1.234,56" in extrair_valores_monetarios("O DAS foi R$ 1.234,56 neste mês.")


def test_extrai_multiplos_valores() -> None:
    texto = "Pagamento de R$ 500,00 e R$ 1.200,00"
    valores = extrair_valores_monetarios(texto)
    assert len(valores) == 2


def test_extrai_valor_sem_espacos() -> None:
    valores = extrair_valores_monetarios("Total: R$999,99")
    assert len(valores) == 1
    assert "999,99" in valores[0]


def test_sem_valores_retorna_lista_vazia() -> None:
    assert extrair_valores_monetarios("Sem valores monetários aqui.") == []


# ── extrair_cnpjs ────────────────────────────────────────────────────────────


def test_extrai_cnpj_formatado() -> None:
    cnpjs = extrair_cnpjs("CNPJ: 12.345.678/0001-90")
    assert len(cnpjs) == 1


def test_extrai_dois_cnpjs() -> None:
    texto = "Empresa 12.345.678/0001-90 e fornecedor 98.765.432/0001-10"
    cnpjs = extrair_cnpjs(texto)
    assert len(cnpjs) == 2


def test_sem_cnpj_retorna_lista_vazia() -> None:
    assert extrair_cnpjs("Sem CNPJ aqui.") == []


# ── extrair_datas ────────────────────────────────────────────────────────────


def test_extrai_data_dd_mm_aaaa() -> None:
    datas = extrair_datas("Vencimento em 20/06/2026.")
    assert "20/06/2026" in datas


def test_extrai_data_iso() -> None:
    datas = extrair_datas("Data: 2026-06-20")
    assert "2026-06-20" in datas


def test_extrai_multiplas_datas() -> None:
    texto = "De 01/05/2026 a 31/05/2026"
    datas = extrair_datas(texto)
    assert len(datas) == 2


# ── validar_resposta ─────────────────────────────────────────────────────────


def test_valida_resposta_sem_valores_sem_citacoes() -> None:
    """Texto sem valores monetários e sem citações → válido."""
    resp = _resp("Sua empresa está regular.")
    assert validar_resposta(resp, []) is True


def test_valida_resposta_com_valor_nas_fontes() -> None:
    """Valor monetário no texto aparece na fonte → válido."""
    resp = _resp(
        "O DAS foi R$ 1.234,56.",
        citacoes=[Citacao(fato_id="ap-001", trecho_citado="R$ 1.234,56")],
    )
    fontes = [_fonte("ap-001", "DAS: R$ 1.234,56")]
    assert validar_resposta(resp, fontes) is True


def test_rejeita_valor_nao_nas_fontes() -> None:
    """Valor inventado pelo LLM → inválido."""
    resp = _resp("O DAS foi R$ 5.000,00.")
    fontes = [_fonte("ap-001", "DAS: R$ 1.234,56")]
    assert validar_resposta(resp, fontes) is False


def test_rejeita_citacao_com_id_invalido() -> None:
    """Citação com ID que não existe nas fontes → inválido."""
    resp = _resp(
        "O DAS foi processado [id-fantasma].",
        citacoes=[Citacao(fato_id="id-fantasma", trecho_citado="processado")],
    )
    fontes = [_fonte("ap-001", "DAS: R$ 1.234,56")]
    assert validar_resposta(resp, fontes) is False


def test_valida_citacao_com_id_correto() -> None:
    """Citação com ID válido nas fontes → válido (sem valor monetário)."""
    resp = _resp(
        "Empresa regular [sit-001].",
        citacoes=[Citacao(fato_id="sit-001", trecho_citado="regular")],
    )
    fontes = [_fonte("sit-001", "Situação: regular", tipo="situacao_fiscal")]
    assert validar_resposta(resp, fontes) is True


def test_rejeita_cnpj_nao_nas_fontes() -> None:
    """CNPJ inventado → inválido."""
    resp = _resp("Empresa CNPJ 99.999.999/0001-99")
    fontes = [_fonte("empr-001", "CNPJ: 12.345.678/0001-90", tipo="empresa")]
    assert validar_resposta(resp, fontes) is False


def test_valida_cnpj_nas_fontes() -> None:
    """CNPJ presente nas fontes → válido."""
    resp = _resp("CNPJ 12.345.678/0001-90 está regular.")
    fontes = [_fonte("empr-001", "CNPJ: 12.345.678/0001-90")]
    assert validar_resposta(resp, fontes) is True


def test_rejeita_data_nao_nas_fontes() -> None:
    """Data inventada → inválido."""
    resp = _resp("Vence em 31/12/2026.")
    fontes = [_fonte("ag-001", "Vencimento: 20/06/2026", tipo="agenda")]
    assert validar_resposta(resp, fontes) is False


def test_valida_data_nas_fontes() -> None:
    """Data presente nas fontes → válido."""
    resp = _resp("DAS vence em 20/06/2026 [ag-001].",
                 citacoes=[Citacao(fato_id="ag-001", trecho_citado="20/06/2026")])
    fontes = [_fonte("ag-001", "Vencimento: 20/06/2026", tipo="agenda")]
    assert validar_resposta(resp, fontes) is True


def test_resposta_padrao_verificar_nao_vazia() -> None:
    """Constante de resposta padrão deve ser uma string não-vazia em PT-BR."""
    assert isinstance(RESPOSTA_PADRAO_VERIFICAR, str)
    assert len(RESPOSTA_PADRAO_VERIFICAR) > 20
    assert "verificar" in RESPOSTA_PADRAO_VERIFICAR.lower() or "contador" in RESPOSTA_PADRAO_VERIFICAR.lower()


# ── detectar_out_of_scope ────────────────────────────────────────────────────


@pytest.mark.parametrize("pergunta,esperado_out,esperada_cat", [
    ("Como me defender de um auto de infração?", True, "contencioso_fiscal"),
    ("Quero abrir uma holding familiar", True, "societario"),
    ("Reduzir impostos com planejamento tributário", True, "planejamento_tributario"),
    ("Quero fazer importação com drawback", True, "operacoes_complexas"),
    ("Quanto pago de DAS em maio?", False, None),
    ("Quando vence o PGDAS-D?", False, None),
    ("Qual meu regime tributário?", False, None),
    ("Quero emitir uma nota fiscal", False, None),
    ("Tenho problema de CARF", True, "contencioso_fiscal"),
    ("Fusão de empresas", True, "societario"),
    ("Substituição tributária ICMS-ST", True, "operacoes_complexas"),
    # "holding" é detectado antes de "elisão fiscal" (societario tem prioridade por ordem)
    ("Elisão fiscal para holding familiar", True, "societario"),
])
def test_detectar_out_of_scope(
    pergunta: str, esperado_out: bool, esperada_cat: str | None
) -> None:
    eh_out, categoria = detectar_out_of_scope(pergunta)
    assert eh_out == esperado_out, f"Pergunta '{pergunta}': esperado out={esperado_out}"
    if esperada_cat:
        assert categoria == esperada_cat


def test_pergunta_vazia_nao_e_out_of_scope() -> None:
    eh_out, cat = detectar_out_of_scope("")
    assert eh_out is False
    assert cat is None


def test_pergunta_in_scope_retorna_none_categoria() -> None:
    eh_out, cat = detectar_out_of_scope("Quanto pago de DAS?")
    assert eh_out is False
    assert cat is None
