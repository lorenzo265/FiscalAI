"""Interface dos scrapers CRF (Caixa) + CNDT (TST) — Sprint 19.6 PR1 #3.

**Refactor estrutural sem implementação de scraping real.** Substitui o
skeleton inline de ``service.py::_emitir_skeleton`` por uma interface
clara (``Protocol``) + adapter padrão (``NotImplementedScraper``) que
deixa o ponto de extensão pronto pra plugar um provider real quando o
projeto decidir a stack (Playwright headless + 2captcha/anti-captcha
provider OU integração com SERPRO se passarem a expor essas certidões).

**Estado atual (PR1 honesto):**

  * Interface ``CrfScraper`` / ``CndtScraper`` cravada — qualquer
    implementação respeita o contrato.
  * ``NotImplementedScraper`` é o adapter padrão injetado pelo router
    quando ``settings.CRF_SCRAPER_PROVIDER`` e
    ``settings.CNDT_SCRAPER_PROVIDER`` não estão configurados.
  * Service ``CertidoesService`` aceita scrapers por DI — sem scraper
    cai no comportamento legado (status='processando' + mensagem
    operacional para fallback manual).
  * Quando admin configurar provider real (Sprint 19.6 PR3 + decisão
    de stack), instancia adapter respectivo e DI funciona end-to-end.

**Gate operacional não-código (pendência rastreada):**

  1. Decidir provider de captcha (2captcha vs anti-captcha vs
     manual-via-painel-admin).
  2. ``poetry add playwright`` (~300MB binários) ou alternativa leve.
  3. Implementar ``PlaywrightCrfScraper`` / ``PlaywrightCndtScraper``.
  4. Settings ``CRF_SCRAPER_PROVIDER='playwright'`` ativa adapter.
  5. Storage S3 (depende de pendência #2) pra persistir PDF baixado.

Princípios cravados:

  * §8.6 re-check — adapter recebe ``idempotency_key`` e Service
    valida ``numero`` retornado contra regex CRF/CNDT.
  * §8.10 observabilidade — adapter logga structured ``crf.scrape.*``
    e ``cndt.scrape.*``.
  * §8.11 out-of-scope declarado — ``NotImplementedScraper`` deixa
    explícito que o gate é externo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import structlog

from app.shared.exceptions import CertidaoEmissaoFalhou

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CertidaoExtraida:
    """Resultado de um scrape bem-sucedido — dados normalizados.

    Sem PDF ainda (storage S3 vem do PR3 da mesma sprint). Caller
    aceita ``pdf_base64=None`` e marca ``storage_key=None`` quando
    storage não estiver pronto.
    """

    numero: str
    valid_until: date | None
    status_normalizado: str  # "negativa" | "positiva" | "positiva_com_efeitos_de_negativa"
    pdf_base64: str | None = None
    payload_bruto: dict[str, str] | None = None  # diagnóstico


class CrfScraper(Protocol):
    """Contrato do adapter que consulta CRF da Caixa.

    Implementação real deve:

      * Resolver reCAPTCHA via provider externo.
      * Submeter formulário com ``cnpj``.
      * Parsear resposta HTML pro ``CertidaoExtraida``.
      * Levantar ``CertidaoEmissaoFalhou`` em qualquer erro (resposta
        irregular, captcha falhou, timeout). Caller marca status='erro'.
    """

    async def emitir(
        self, cnpj: str, *, idempotency_key: str
    ) -> CertidaoExtraida: ...


class CndtScraper(Protocol):
    """Contrato do adapter que consulta CNDT do TST. Análogo a ``CrfScraper``."""

    async def emitir(
        self, cnpj: str, *, idempotency_key: str
    ) -> CertidaoExtraida: ...


class NotImplementedScraper:
    """Adapter padrão — levanta ``CertidaoEmissaoFalhou`` sinalizando
    gate operacional (decisão de stack + provider de captcha) sem
    quebrar o pipeline.

    Service captura e marca status='processando' com mensagem operacional
    (fallback manual no painel Caixa/TST). UX antiga preservada;
    arquitetura nova pronta pra ativação.
    """

    def __init__(self, *, tipo: str) -> None:
        self._tipo = tipo  # "CRF" | "CNDT" — só pra log estruturado

    async def emitir(
        self, cnpj: str, *, idempotency_key: str
    ) -> CertidaoExtraida:
        log.info(
            "certidao.scraper.nao_configurado",
            tipo=self._tipo,
            cnpj_prefixo=cnpj[:8],
        )
        raise CertidaoEmissaoFalhou(
            f"Scraper {self._tipo} não configurado — decisão de stack "
            f"pendente (Playwright + provider captcha). Veja "
            f"`app/modules/certidoes/scrapers.py` ou `log_agente.md` #3."
        )


__all__ = [
    "CertidaoExtraida",
    "CndtScraper",
    "CrfScraper",
    "NotImplementedScraper",
]
