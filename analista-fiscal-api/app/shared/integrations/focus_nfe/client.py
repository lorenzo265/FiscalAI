from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_SANDBOX_URL = "https://homologacao.focusnfe.com.br"
_PROD_URL = "https://api.focusnfe.com.br"


class FocusNfeClient:
    """Cliente assíncrono para Focus NFe — emissão e consulta de NFS-e.

    Idempotência: toda emissão usa `idempotency_key` no parâmetro `ref`.
    Retry: apenas erros de transporte (não 4xx/5xx da API).
    """

    def __init__(self, settings: Settings) -> None:
        self._base = _SANDBOX_URL if settings.FOCUS_NFE_SANDBOX else _PROD_URL
        self._http = httpx.AsyncClient(
            auth=(settings.FOCUS_NFE_TOKEN, ""),
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def emitir_nfse(
        self,
        payload: JsonObject,
        *,
        idempotency_key: str,
    ) -> JsonObject:
        """POST /v2/nfse?ref={key} — emite NFS-e.

        Idempotente: chamadas repetidas com o mesmo `idempotency_key` são no-op.
        Retorna o dict do Focus NFe com pelo menos `status` e `ref`.
        """
        url = f"{self._base}/v2/nfse"
        try:
            resp = await self._http.post(url, params={"ref": idempotency_key}, json=payload)
        except httpx.TransportError as exc:
            from app.shared.exceptions import FocusNfeTimeout

            raise FocusNfeTimeout(f"Timeout na Focus NFe: {exc}") from exc

        if resp.status_code in {200, 201, 202}:
            data: JsonObject = resp.json()
            log.info(
                "focus_nfe.nfse.emitida",
                ref=idempotency_key,
                status=data.get("status"),
            )
            return data

        from app.shared.exceptions import FocusNfeErro

        raise FocusNfeErro(
            f"Focus NFe retornou {resp.status_code}: {resp.text[:300]}"
        )

    async def consultar_nfse(self, ref: str) -> JsonObject:
        """GET /v2/nfse/{ref} — consulta status de NFS-e emitida."""
        url = f"{self._base}/v2/nfse/{ref}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            from app.shared.exceptions import FocusNfeTimeout

            raise FocusNfeTimeout(f"Timeout na Focus NFe: {exc}") from exc

        if resp.status_code == 404:
            from app.shared.exceptions import NfseNaoEncontrada

            raise NfseNaoEncontrada(f"NFS-e '{ref}' não encontrada na Focus NFe")

        resp.raise_for_status()
        result: JsonObject = resp.json()
        return result
