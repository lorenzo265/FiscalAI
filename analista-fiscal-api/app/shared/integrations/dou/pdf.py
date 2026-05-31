"""Extração de texto de PDFs do DOU via ``pdfplumber`` (Sprint 19.5 PR3).

Import lazy: ``pdfplumber`` é dependência opt-in (pesada — depende de
``pdfminer.six``). Só importamos quando a função é chamada de fato.
Ambientes que não rodam o worker (testes unitários, CI sem deps de PDF)
não pagam o custo.

Função pura: aceita bytes do PDF + opções, devolve dict
``{paginas: [{numero, texto}], texto_total}``. Sem I/O — caller é
responsável por baixar o PDF via ``DouClient``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Apenas para mypy — ``pdfplumber`` não roda em CI base.
    pass


@dataclass(frozen=True, slots=True)
class PaginaExtraida:
    numero: int  # 1-indexed
    texto: str


@dataclass(frozen=True, slots=True)
class PdfExtraido:
    paginas: list[PaginaExtraida]
    texto_total: str


class PdfPlumberAusente(RuntimeError):
    """``pdfplumber`` não está instalado no ambiente.

    Worker captura e marca a sugestão como ``rejeitada`` com motivo
    operacional — não é caso normal em prod (Sprint 19.5 PR3 adiciona
    pdfplumber a pyproject.toml).
    """


def extrair_texto_pdf(pdf_bytes: bytes) -> PdfExtraido:
    """Extrai texto página-a-página. ``pdfplumber`` é importado aqui
    para preservar import-time leve no resto do app.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise PdfPlumberAusente(
            "pdfplumber não instalado — adicione `poetry add pdfplumber` "
            "ou rode o worker em ambiente com a dep."
        ) from exc

    import io

    paginas: list[PaginaExtraida] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, p in enumerate(pdf.pages, start=1):
            texto = p.extract_text() or ""
            paginas.append(PaginaExtraida(numero=idx, texto=texto))
    texto_total = "\n".join(p.texto for p in paginas)
    return PdfExtraido(paginas=paginas, texto_total=texto_total)


__all__ = [
    "PaginaExtraida",
    "PdfExtraido",
    "PdfPlumberAusente",
    "extrair_texto_pdf",
]
