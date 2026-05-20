"""Cliente HTTP do SERPRO Integra Contador.

Cobre os serviços usados na Sprint 6: emissão de certidões (CND) e — a partir
do PR2 — PGDAS-D, e-CAC, DCTFWeb. Cada chamada:

  1. obtém access_token via :class:`SerproOAuthClient` (cache Redis)
  2. envia POST/GET com `idempotency_key` no header `X-Request-Tag`
  3. retorna :class:`SerproResponse` no formato Integra Contador

Princípios aplicados (§7.1, §8.9, §8.10 do Plano):

* Idempotência: chave determinística por (empresa, serviço, contexto temporal)
* Retry exponencial só em erros de transporte; 4xx/5xx do SERPRO sobem como
  ``SerproErro`` para tratamento explícito no service.
* Audit: cada chamada registra status_http + latência (persistência fica no
  service para incluir tenant_id sob RLS).
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import cast

import httpx
import redis.asyncio as redis_async
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.exceptions import SerproErro, SerproTimeout
from app.shared.integrations.serpro.oauth import SerproOAuthClient
from app.shared.integrations.serpro.types import (
    SerproDadosDeclaracao,
    SerproResponse,
)

log = structlog.get_logger(__name__)

# Endpoints Integra Contador — caminhos seguem o padrão público da SERPRO.
# Refs: https://apicenter.estaleiro.serpro.gov.br
_PATH_EMITIR = "/integra-contador/v1/Emitir"
_PATH_APOIAR = "/integra-contador/v1/Apoiar"
_PATH_CONSULTAR = "/integra-contador/v1/Consultar"
_PATH_DECLARAR = "/integra-contador/v1/Declarar"


class SerproClient:
    """Cliente assíncrono do SERPRO Integra Contador.

    Métodos retornam o payload Integra Contador puro (decodificado de
    ``dados`` quando a SERPRO devolve JSON aninhado).
    """

    def __init__(
        self,
        settings: Settings,
        redis: redis_async.Redis[str] | None,
        *,
        http: httpx.AsyncClient | None = None,
        oauth: SerproOAuthClient | None = None,
    ) -> None:
        self._base_url = settings.SERPRO_BASE_URL.rstrip("/")
        self._sandbox = settings.SERPRO_SANDBOX
        self._http = http or httpx.AsyncClient(timeout=45.0)
        self._owns_http = http is None
        self._oauth = oauth or SerproOAuthClient(settings, redis, http=self._http)
        self._owns_oauth = oauth is None

    async def aclose(self) -> None:
        if self._owns_oauth:
            await self._oauth.aclose()
        if self._owns_http:
            await self._http.aclose()

    # ── Certidões ────────────────────────────────────────────────────────────

    async def emitir_certidao_cnd(
        self,
        cnpj: str,
        *,
        idempotency_key: str,
    ) -> SerproResponse:
        """Emite Certidão Negativa de Débitos federal (RFB/PGFN) via SERPRO.

        Retorna dict com pelo menos ``status``, ``numero``, ``valid_until``
        e — quando disponível — ``pdf_base64`` para storage.
        """
        payload = {
            "contratante": {"numero": cnpj, "tipo": 2},
            "autorPedidoDados": {"numero": cnpj, "tipo": 2},
            "contribuinte": {"numero": cnpj, "tipo": 2},
            "pedidoDados": {
                "idSistema": "CERTIDOES",
                "idServico": "EMITECERTIDAOCND",
                "versaoSistema": "1.0",
                "dados": "{}",
            },
        }
        return await self._post_json(
            _PATH_EMITIR, payload, idempotency_key=idempotency_key
        )

    # ── PGDAS-D ──────────────────────────────────────────────────────────────

    async def transmitir_pgdas_d(
        self,
        *,
        cnpj: str,
        periodo_apuracao: str,
        dados_declaracao: SerproDadosDeclaracao,
        idempotency_key: str,
    ) -> SerproResponse:
        """Transmite PGDAS-D (declaração SN mensal) via Integra Contador.

        Args:
            cnpj: CNPJ do contribuinte (14 dígitos sem máscara).
            periodo_apuracao: Competência no formato "AAAAMM" (ex.: "202604").
            dados_declaracao: Payload específico da declaração SN —
                receitas por estabelecimento, deduções, regimes especiais, etc.
                Em produção esse dict é montado a partir da `ApuracaoFiscal`.
            idempotency_key: Chave determinística por (empresa, competência) que
                garante que retransmissões caiam no lock do SERPRO sem custo
                duplicado (§8.9).

        Retorna o payload Integra Contador com `dados` contendo, no mínimo,
        ``numeroDeclaracao`` e ``recibo`` quando o status é 200.
        """
        payload = {
            "contratante": {"numero": cnpj, "tipo": 2},
            "autorPedidoDados": {"numero": cnpj, "tipo": 2},
            "contribuinte": {"numero": cnpj, "tipo": 2},
            "pedidoDados": {
                "idSistema": "PGDASD",
                "idServico": "TRANSDECLARACAO11",
                "versaoSistema": "1.0",
                "dados": _json_compact(
                    {"periodoApuracao": periodo_apuracao, **dados_declaracao}
                ),
            },
        }
        return await self._post_json(
            _PATH_DECLARAR, payload, idempotency_key=idempotency_key
        )

    # ── DEFIS / DASN-SIMEI ───────────────────────────────────────────────────

    async def transmitir_defis(
        self,
        *,
        cnpj: str,
        ano_base: int,
        dados_declaracao: SerproDadosDeclaracao,
        idempotency_key: str,
    ) -> SerproResponse:
        """Transmite DEFIS (declaração anual SN) ao Portal do Simples Nacional.

        idSistema/idServico: PGDASD + TRANSDECLDEFIS21 (Manual Integra Contador).
        """
        payload = {
            "contratante": {"numero": cnpj, "tipo": 2},
            "autorPedidoDados": {"numero": cnpj, "tipo": 2},
            "contribuinte": {"numero": cnpj, "tipo": 2},
            "pedidoDados": {
                "idSistema": "PGDASD",
                "idServico": "TRANSDECLDEFIS21",
                "versaoSistema": "1.0",
                "dados": _json_compact(
                    {"anoCalendario": ano_base, **dados_declaracao}
                ),
            },
        }
        return await self._post_json(
            _PATH_DECLARAR, payload, idempotency_key=idempotency_key
        )

    async def transmitir_dasn_simei(
        self,
        *,
        cnpj: str,
        ano_base: int,
        dados_declaracao: SerproDadosDeclaracao,
        idempotency_key: str,
    ) -> SerproResponse:
        """Transmite DASN-SIMEI (declaração anual MEI).

        idSistema/idServico: DASNSIMEI + TRANSDECLARACAO13.
        """
        payload = {
            "contratante": {"numero": cnpj, "tipo": 2},
            "autorPedidoDados": {"numero": cnpj, "tipo": 2},
            "contribuinte": {"numero": cnpj, "tipo": 2},
            "pedidoDados": {
                "idSistema": "DASNSIMEI",
                "idServico": "TRANSDECLARACAO13",
                "versaoSistema": "1.0",
                "dados": _json_compact(
                    {"anoCalendario": ano_base, **dados_declaracao}
                ),
            },
        }
        return await self._post_json(
            _PATH_DECLARAR, payload, idempotency_key=idempotency_key
        )

    # ── e-CAC (caixa postal RFB) ─────────────────────────────────────────────

    async def listar_caixa_postal_e_cac(
        self,
        *,
        cnpj: str,
        idempotency_key: str,
        somente_nao_lidas: bool = True,
    ) -> SerproResponse:
        """Lista mensagens da caixa postal e-CAC do contribuinte.

        Args:
            cnpj: CNPJ do contribuinte.
            idempotency_key: Determinística por (empresa, data, indicador).
            somente_nao_lidas: Filtra mensagens não-lidas (padrão).

        Retorno: payload Integra Contador com `dados.mensagens` (lista).
        """
        payload = {
            "contratante": {"numero": cnpj, "tipo": 2},
            "autorPedidoDados": {"numero": cnpj, "tipo": 2},
            "contribuinte": {"numero": cnpj, "tipo": 2},
            "pedidoDados": {
                "idSistema": "CAIXAPOSTAL",
                "idServico": "MSGCONTRIBUINTE51",
                "versaoSistema": "1.0",
                "dados": _json_compact({"indicadorLeitura": 1 if somente_nao_lidas else 0}),
            },
        }
        return await self._post_json(
            _PATH_CONSULTAR, payload, idempotency_key=idempotency_key
        )

    # ── HTTP base ────────────────────────────────────────────────────────────

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _post_json(
        self,
        path: str,
        payload: Mapping[str, object],
        *,
        idempotency_key: str,
    ) -> SerproResponse:
        token = await self._oauth.access_token()
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-Tag": idempotency_key,
        }
        inicio = time.monotonic()
        try:
            resp = await self._http.post(url, json=payload, headers=headers)
        except httpx.TransportError as exc:
            raise SerproTimeout(f"Timeout SERPRO em {path}: {exc}") from exc

        latencia_ms = int((time.monotonic() - inicio) * 1000)

        # Token expirou entre cache e request — invalida e propaga p/ retry alto.
        if resp.status_code == 401:
            await self._oauth.invalidar()
            raise SerproErro(
                f"SERPRO {path} retornou 401 (token expirado/inválido)"
            )

        if resp.status_code >= 400:
            log.warning(
                "serpro.call.erro",
                path=path,
                status_http=resp.status_code,
                latencia_ms=latencia_ms,
                idempotency_key=idempotency_key,
                corpo=resp.text[:300],
            )
            raise SerproErro(
                f"SERPRO {path} retornou {resp.status_code}: {resp.text[:300]}"
            )

        log.info(
            "serpro.call.ok",
            path=path,
            status_http=resp.status_code,
            latencia_ms=latencia_ms,
            idempotency_key=idempotency_key,
        )
        body = cast(SerproResponse, resp.json())
        return body


def _json_compact(value: SerproDadosDeclaracao) -> str:
    """Serializa Mapping como JSON compacto — formato esperado em `pedidoDados.dados`."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
