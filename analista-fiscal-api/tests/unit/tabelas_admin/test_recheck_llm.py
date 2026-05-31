"""Testes do re-check determinístico §8.6 pós-LLM (Sprint 19.5 PR3)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.tabelas_admin.recheck_llm import (
    CitacaoLLM,
    rechecar_extracao_llm,
)

from tests.unit.tabelas_admin._helpers import (
    faixas_inss_2026,
)


_PAYLOAD_INSS_VALIDO: dict[str, object] = {
    "valid_from": "2026-01-15",
    "fonte_norma": "Portaria MPS/MF 1/2026, DOU 2026-01-15 seção 1 página 42",
    "faixas": [
        {
            "tipo": f.tipo,
            "faixa": f.faixa,
            "valor_ate": str(f.valor_ate),
            "aliquota": str(f.aliquota),
        }
        for f in faixas_inss_2026()
    ],
}

_PDF_INSS_REPRESENTATIVO = """
ART. 1º A contribuição previdenciária dos segurados empregado, empregado
doméstico e trabalhador avulso será calculada mediante a aplicação da
correspondente alíquota, conforme tabela abaixo.

Tabela: até R$ 1.620,00 — 7,5%; de R$ 1.620,01 a R$ 2.966,68 — 9,0%;
de R$ 2.966,69 a R$ 4.450,02 — 12,0%; de R$ 4.450,03 a R$ 8.530,06 — 14,0%.

Vigência a partir de 1º de janeiro de 2026.
"""


def test_recheck_payload_canonico_passou() -> None:
    citacoes = [
        CitacaoLLM(pagina=1, trecho="ART. 1º A contribuição previdenciária"),
        CitacaoLLM(pagina=1, trecho="Tabela: até R$ 1.620,00 — 7,5%"),
        CitacaoLLM(pagina=1, trecho="Vigência a partir de 1º de janeiro de 2026"),
    ]
    r = rechecar_extracao_llm(
        tipo_tabela="inss",
        payload_llm=_PAYLOAD_INSS_VALIDO,
        citacoes_llm=citacoes,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS_REPRESENTATIVO,
    )
    assert r.passou is True
    assert r.observacoes.get("citacoes_validas") == 3


def test_recheck_falha_quando_payload_quebra_validador_pr1() -> None:
    """Aliquota INSS 0.75 (typo) — validador PR1 captura."""
    payload = dict(_PAYLOAD_INSS_VALIDO)
    faixas_quebradas = [dict(f) for f in payload["faixas"]]  # type: ignore[arg-type]
    faixas_quebradas[0]["aliquota"] = "0.75"  # 75% — implausível
    payload["faixas"] = faixas_quebradas
    citacoes = [
        CitacaoLLM(pagina=1, trecho="ART. 1º A contribuição previdenciária"),
        CitacaoLLM(pagina=1, trecho="Tabela: até R$ 1.620,00"),
        CitacaoLLM(pagina=1, trecho="Vigência a partir de 1º de janeiro"),
    ]
    r = rechecar_extracao_llm(
        tipo_tabela="inss",
        payload_llm=payload,
        citacoes_llm=citacoes,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS_REPRESENTATIVO,
    )
    assert r.passou is False
    falhas = r.observacoes.get("falhas", [])
    assert any(f.get("codigo") == "validador_pr1_falhou" for f in falhas)  # type: ignore[union-attr]


def test_recheck_falha_quando_menos_de_3_citacoes_literais() -> None:
    """LLM devolveu só 1 citação que casa literalmente — re-check rejeita."""
    citacoes = [
        CitacaoLLM(pagina=1, trecho="ART. 1º A contribuição previdenciária"),
        # 2 citações que NÃO aparecem no PDF
        CitacaoLLM(pagina=1, trecho="texto inventado que não está no DOU"),
        CitacaoLLM(pagina=1, trecho="outra citação fabricada pelo LLM"),
    ]
    r = rechecar_extracao_llm(
        tipo_tabela="inss",
        payload_llm=_PAYLOAD_INSS_VALIDO,
        citacoes_llm=citacoes,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS_REPRESENTATIVO,
    )
    assert r.passou is False
    assert r.observacoes["citacoes_validas"] == 1
    falhas = r.observacoes.get("falhas", [])
    assert any(f.get("codigo") == "citacoes_insuficientes" for f in falhas)  # type: ignore[union-attr]


def test_recheck_falha_quando_confianca_baixa() -> None:
    citacoes = [
        CitacaoLLM(pagina=1, trecho="ART. 1º A contribuição previdenciária"),
        CitacaoLLM(pagina=1, trecho="Tabela: até R$ 1.620,00"),
        CitacaoLLM(pagina=1, trecho="Vigência a partir de 1º de janeiro"),
    ]
    r = rechecar_extracao_llm(
        tipo_tabela="inss",
        payload_llm=_PAYLOAD_INSS_VALIDO,
        citacoes_llm=citacoes,
        confianca_llm=Decimal("0.3"),  # < 0.5
        texto_pdf=_PDF_INSS_REPRESENTATIVO,
    )
    assert r.passou is False
    falhas = r.observacoes.get("falhas", [])
    assert any(f.get("codigo") == "confianca_baixa" for f in falhas)  # type: ignore[union-attr]


def test_recheck_falha_quando_payload_estrutural_invalido() -> None:
    """LLM devolveu JSON com schema errado — Pydantic captura."""
    payload_quebrado = {
        "valid_from": "2026-01-15",
        "fonte_norma": "Portaria MPS/MF 1/2026, DOU 2026-01-15 página 42",
        "faixas": "isso devia ser uma lista, não string",
    }
    r = rechecar_extracao_llm(
        tipo_tabela="inss",
        payload_llm=payload_quebrado,
        citacoes_llm=[],
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS_REPRESENTATIVO,
    )
    assert r.passou is False
    falhas = r.observacoes.get("falhas", [])
    assert any(  # type: ignore[union-attr]
        f.get("codigo") == "pydantic_validation_falhou" for f in falhas
    )
