"""Cliente DOU para o worker ``tabelas.varrer_dou_mensal`` (Sprint 19.5 PR3).

Apenas leitura. A API JSON do DOU é semi-pública sem SLA — o cliente é
**fail-soft** por design:

  * Timeout 30s + 3 retries com jitter.
  * Resposta não-200 → ``DouIndisponivel`` (resiliente; worker loga e segue).
  * Resposta com schema inesperado → lista vazia + log warn.
  * Sem cache Redis nesta iteração — varredura é mensal, sem ganho real
    de cache.

Não validamos o conteúdo das matérias aqui — quem extrai a Portaria do
PDF é o re-check determinístico + LLM no service da Camada 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.shared.exceptions import DouIndisponivel

log = structlog.get_logger(__name__)


_BASE_URL = "https://www.in.gov.br"


@dataclass(frozen=True, slots=True)
class MateriaDou:
    """Matéria publicada no DOU referenciada pelo worker.

    Campos extraídos da API JSON do DOU. Quando o schema upstream muda,
    o parser deve degradar graciosamente para campos ausentes (``None``).
    """

    titulo: str
    url_html: str
    url_pdf: str | None
    data_publicacao: date
    secao: str | None  # "Seção 1", "Seção 2", etc.


class DouClient:
    """Cliente assíncrono mínimo para buscar matérias DOU."""

    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        # ``http_client`` injetável para testes — passamos transport mockado.
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0)
        )
        self._owns_http = http_client is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def buscar_materias(
        self, *, termo: str, desde: date
    ) -> list[MateriaDou]:
        """Devolve matérias casando ``termo`` publicadas em/após ``desde``.

        ``termo`` é texto livre — ex.: ``"Portaria MPS/MF" AND "INSS"``.
        Resposta vazia (sem hits) é caso normal, não erro.
        """
        url = f"{self._base}/consulta"
        params = {
            "q": termo,
            "publishFrom": desde.strftime("%d/%m/%Y"),
        }
        try:
            resp = await self._http.get(url, params=params)
        except httpx.TransportError as exc:
            log.warning("dou.busca.transport_error", termo=termo, erro=str(exc))
            raise DouIndisponivel(
                f"DOU inacessível após retries: {exc}"
            ) from exc

        if resp.status_code != 200:
            log.warning(
                "dou.busca.status_inesperado",
                status=resp.status_code,
                termo=termo,
            )
            raise DouIndisponivel(
                f"DOU devolveu status {resp.status_code}"
            )

        try:
            data = resp.json()
        except ValueError:
            log.warning("dou.busca.json_invalido", termo=termo)
            return []

        return _parsear_resposta(data)


def _parsear_resposta(data: object) -> list[MateriaDou]:
    """Extrai a lista de matérias do payload — defensivo contra schema mudado.

    Formato observado em 2026-05: ``{"jornal": [{"titulo": ..., "url_pdf": ...,
    "dataPublicacao": "DD/MM/YYYY", "secao": "1"}]}``. Se mudar, devolve [].
    """
    if not isinstance(data, dict):
        return []
    materias_raw = data.get("jornal") or data.get("items") or []
    if not isinstance(materias_raw, list):
        return []

    materias: list[MateriaDou] = []
    for item in materias_raw:
        if not isinstance(item, dict):
            continue
        titulo = item.get("titulo") or item.get("title")
        url_html = item.get("urlHtml") or item.get("url") or ""
        url_pdf = item.get("urlPdf") or item.get("urlPdfMateria")
        data_pub_raw = item.get("dataPublicacao") or item.get("publishedAt")
        secao = item.get("secao") or item.get("section")
        if not (isinstance(titulo, str) and isinstance(url_html, str)):
            continue
        data_pub = _parsear_data(data_pub_raw)
        if data_pub is None:
            continue
        materias.append(
            MateriaDou(
                titulo=titulo,
                url_html=url_html,
                url_pdf=url_pdf if isinstance(url_pdf, str) else None,
                data_publicacao=data_pub,
                secao=secao if isinstance(secao, str) else None,
            )
        )
    return materias


def _parsear_data(raw: object) -> date | None:
    """Aceita DD/MM/YYYY ou ISO YYYY-MM-DD. None se inválido."""
    if not isinstance(raw, str):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


__all__ = ["DouClient", "MateriaDou"]
