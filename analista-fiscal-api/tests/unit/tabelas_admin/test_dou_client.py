"""Testes do parser DOU — defensivo contra schema mudado (Sprint 19.5 PR3)."""

from __future__ import annotations

from datetime import date

from app.shared.integrations.dou.client import _parsear_resposta


def test_parsea_payload_canonico() -> None:
    data = {
        "jornal": [
            {
                "titulo": "Portaria MPS/MF nº 1, de 15 de janeiro de 2026",
                "urlHtml": "https://in.gov.br/web/dou/-/portaria-1-2026",
                "urlPdf": "https://in.gov.br/web/dou/-/portaria-1-2026.pdf",
                "dataPublicacao": "15/01/2026",
                "secao": "Seção 1",
            }
        ]
    }
    materias = _parsear_resposta(data)
    assert len(materias) == 1
    m = materias[0]
    assert "Portaria MPS/MF" in m.titulo
    assert m.url_pdf is not None
    assert m.data_publicacao == date(2026, 1, 15)


def test_parsea_schema_alternativo_items_em_vez_de_jornal() -> None:
    """API pode mudar o nome do envelope — aceitamos ``items`` também."""
    data = {
        "items": [
            {
                "title": "Lei 15.123/2026",
                "url": "https://in.gov.br/x",
                "urlPdfMateria": "https://in.gov.br/x.pdf",
                "publishedAt": "2026-02-10",
                "section": "1",
            }
        ]
    }
    materias = _parsear_resposta(data)
    assert len(materias) == 1
    assert materias[0].data_publicacao == date(2026, 2, 10)


def test_parsea_resposta_vazia_devolve_lista_vazia() -> None:
    assert _parsear_resposta({"jornal": []}) == []
    assert _parsear_resposta({}) == []


def test_parsea_resposta_invalida_nao_quebra() -> None:
    """Schema completamente errado — devolve [] sem levantar."""
    assert _parsear_resposta("não é dict") == []
    assert _parsear_resposta(None) == []
    assert _parsear_resposta({"jornal": "string em vez de lista"}) == []


def test_parsea_pula_itens_com_data_invalida() -> None:
    data = {
        "jornal": [
            {
                "titulo": "Item 1 — válido",
                "urlHtml": "https://in.gov.br/1",
                "urlPdf": "https://in.gov.br/1.pdf",
                "dataPublicacao": "15/01/2026",
                "secao": "Seção 1",
            },
            {
                "titulo": "Item 2 — data quebrada",
                "urlHtml": "https://in.gov.br/2",
                "dataPublicacao": "data inválida",
            },
        ]
    }
    materias = _parsear_resposta(data)
    assert len(materias) == 1
    assert materias[0].titulo == "Item 1 — válido"
