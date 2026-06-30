"""Providers para o serviço DistribuiçãoDFe (NFeDistribuicaoDFe) — MD-e PR2.

Expõe:
  * ``SefazMdeProvider`` — Protocol (contrato; zero importações de rede).
  * ``_FakeSefazMdeProvider`` — determinístico, dev/CI, sem rede.
  * ``FocusSefazMdeProvider`` — real, via Focus NFe REST (best-effort [follow-up]).
  * ``build_sefaz_mde_provider`` — factory baseado em settings.

§8.12 — transmissão é ato consciente. ``transmitir_evento`` é NotImplemented
         neste PR (PR3 cabeará cert A1 + RecepcaoEvento SEFAZ).
§8.9  — idempotência: o caller (``DistribuicaoService``) faz upsert idempotente;
         o provider não persiste nada.

[follow-up PR3] Confirmar o endpoint Focus NFe para NF-es recebidas por NSU
  antes de ligar em produção. O Focus NFe pode não ter um wrapper REST para
  NFeDistribuicaoDFe e exigir integração direta com o SOAP SEFAZ.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.integrations.sefaz_mde.types import (
    ResultadoDistribuicao,
    ResumoNFeDestinada,
    TipoDocumentoMde,
)

log = structlog.get_logger(__name__)

# Tamanho do lote gerado pelo provider fake por chamada (3 docs/página)
_FAKE_BATCH_SIZE: int = 3


@runtime_checkable
class SefazMdeProvider(Protocol):
    """Contrato do provider DistribuiçãoDFe.

    Cada implementação segue:
      * ``baixar_documentos`` — consulta paginada por NSU, retorna lote.
      * ``transmitir_evento`` — envia evento ao RecepcaoEvento SEFAZ (PR3).

    O caller (DistribuicaoService) é responsável pela persistência e pelo
    controle de NSU — o provider é stateless.
    """

    async def baixar_documentos(
        self,
        cnpj: str,
        ult_nsu: int,
    ) -> ResultadoDistribuicao:
        """Consulta documentos de interesse a partir de ``ult_nsu``.

        Retorna até um lote (50 documentos, conforme DistribuiçãoDFe) com o
        ``ult_nsu`` avançado e o ``max_nsu`` corrente do Ambiente Nacional.
        """
        ...

    async def transmitir_evento(
        self,
        cnpj: str,
        xml_evento: bytes,
        idempotency_key: str,
    ) -> str:
        """Envia evento MD-e ao RecepcaoEvento SEFAZ. Retorna protocolo.

        TODO PR3 — não implementado neste PR. Cabeará cert A1 ICP-Brasil +
        wiring do webservice NFeRecepcaoEvento (cOrgao=91, Ambiente Nacional).
        """
        ...


class _FakeSefazMdeProvider:
    """Provider determinístico para dev/CI (sem rede, sem DB).

    Gera ``_FAKE_BATCH_SIZE`` resumos por chamada a partir de ``ult_nsu + 1``.

    Comportamento por ``extra_batches``:
      * 0 (default): uma única página termina o ciclo (``ult_nsu == max_nsu``
        após a chamada — o loop de sincronização para).
      * N > 0: simula N páginas adicionais (``max_nsu > ult_nsu + batch_size``),
        útil para testar o cap ``max_paginas`` e ``truncado=True``.

    Mesma entrada → mesma saída (determinismo §8.4). Sem rede, sem estado.
    """

    def __init__(self, *, extra_batches: int = 0) -> None:
        self._extra = extra_batches

    async def baixar_documentos(
        self,
        cnpj: str,
        ult_nsu: int,
    ) -> ResultadoDistribuicao:
        docs: list[ResumoNFeDestinada] = []
        for i in range(1, _FAKE_BATCH_SIZE + 1):
            nsu = ult_nsu + i
            chave = self._chave_para_nsu(nsu)
            docs.append(
                ResumoNFeDestinada(
                    chave_nfe=chave,
                    nsu=nsu,
                    emitente_cnpj="12345678000195",
                    emitente_nome=f"Emitente Fake {nsu}",
                    valor_total=Decimal("1000.00") + Decimal(str(nsu)),
                    dh_emissao=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
                    tipo_documento="resumo",
                    xml_completo=None,
                )
            )
        novo_ult_nsu = ult_nsu + _FAKE_BATCH_SIZE
        max_nsu = novo_ult_nsu + _FAKE_BATCH_SIZE * self._extra
        log.debug(
            "sefaz_mde.fake.baixar",
            ult_nsu_entrada=ult_nsu,
            novo_ult_nsu=novo_ult_nsu,
            max_nsu=max_nsu,
            docs=len(docs),
        )
        return ResultadoDistribuicao(
            documentos=docs,
            ult_nsu=novo_ult_nsu,
            max_nsu=max_nsu,
        )

    async def transmitir_evento(
        self,
        cnpj: str,
        xml_evento: bytes,
        idempotency_key: str,
    ) -> str:
        raise NotImplementedError(
            "transmitir_evento: implementar em PR3 (cert A1 + RecepcaoEvento SEFAZ)"
        )

    @staticmethod
    def _chave_para_nsu(nsu: int) -> str:
        """Gera chave NF-e fictícia de 44 dígitos a partir do NSU."""
        # Prefixo determinístico: cUF(2)+AAMM(4)+CNPJ(14)+mod(2)+serie(3)+nNF(9)
        # Coloca o NSU nos últimos 9 dígitos (nNF) + sufixo aleatório 8 dígitos
        # Garante exatamente 44 dígitos.
        base = f"3526060112345678000195550010{str(nsu).zfill(9)}"
        # Preenche o cDV com um checksum simples (hash dos dígitos disponíveis)
        needed = 44 - len(base)
        suffix = hashlib.sha256(str(nsu).encode()).hexdigest()
        digits = "".join(c for c in suffix if c.isdigit())[:needed]
        digits = digits.ljust(needed, "1")
        return base + digits


class FocusSefazMdeProvider:
    """Provider real via Focus NFe para o DistribuiçãoDFe.

    [follow-up PR3] Os endpoints e o formato de resposta da Focus NFe para
    NF-es recebidas por NSU precisam ser confirmados na documentação oficial
    antes de ligar em produção. A Focus NFe pode não ter um wrapper REST para
    ``NFeDistribuicaoDFe`` — nesse caso esta implementação precisará chamar o
    webservice SOAP da SEFAZ diretamente (endpoint AN).

    Integração real exige ``FOCUS_NFE_TOKEN`` + ambiente ativo.
    Sem token → ``build_sefaz_mde_provider`` retorna o Fake.

    Retry: apenas ``httpx.TransportError`` (erros de transporte).
    4xx/5xx: levanta ``SefazMdeErro`` sem retry (erros de negócio).
    Parser: tolerante a aliases do leiaute (chaveNFe/chave_nfe, CNPJ/cnpj).
    """

    def __init__(self, settings: Settings) -> None:
        self._base = (
            "https://homologacao.focusnfe.com.br"
            if settings.FOCUS_NFE_SANDBOX
            else "https://api.focusnfe.com.br"
        )
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
    async def baixar_documentos(
        self,
        cnpj: str,
        ult_nsu: int,
    ) -> ResultadoDistribuicao:
        """Consulta NF-es recebidas por NSU via Focus NFe.

        [follow-up PR3] Endpoint e formato de resposta a confirmar na doc
        oficial da Focus NFe antes de ir para produção. O endpoint abaixo
        é best-effort baseado no padrão da API Focus NFe (/v2/nfes_recebidas).

        Sem credencial → lança ``SefazMdeErro`` (o caller usa o Fake em dev).
        """
        # [follow-up PR3] Confirmar endpoint + query params exatos na doc Focus NFe.
        # A API pode exigir CNPJ separado ou autenticação diferente por CNPJ.
        url = f"{self._base}/v2/nfes_recebidas"
        params = {"nsu": str(ult_nsu), "cnpj": cnpj}
        try:
            resp = await self._http.get(url, params=params)
        except httpx.TransportError:
            raise  # tenacity captura e decide se retenta

        if resp.status_code == 200:
            return self._parse_response(resp.json(), ult_nsu_consulta=ult_nsu)
        if resp.status_code == 404:
            # Sem documentos disponíveis — cursor já está no topo
            return ResultadoDistribuicao(
                documentos=[], ult_nsu=ult_nsu, max_nsu=ult_nsu
            )

        raise SefazMdeErro(
            f"Focus NFe retornou {resp.status_code}: {resp.text[:300]}",
            status_code=resp.status_code,
        )

    async def transmitir_evento(
        self,
        cnpj: str,
        xml_evento: bytes,
        idempotency_key: str,
    ) -> str:
        raise NotImplementedError(
            "transmitir_evento: implementar em PR3 (cert A1 + RecepcaoEvento SEFAZ)"
        )

    def _parse_response(
        self,
        data: object,
        *,
        ult_nsu_consulta: int,
    ) -> ResultadoDistribuicao:
        """Parse tolerante ao formato JSON da Focus NFe (aliases comuns).

        Aceita variações de chave: ult_nsu/ultNSU, max_nsu/maxNSU,
        documentos/docs/nfes, chave_nfe/chaveNFe/chave_acesso, etc.
        """
        if not isinstance(data, dict):
            raise SefazMdeErro("Resposta não é um objeto JSON")

        ult_nsu = _coerce_int(
            _get_first(data, "ult_nsu", "ultNSU", "ultNsu"), ult_nsu_consulta
        )
        max_nsu = _coerce_int(_get_first(data, "max_nsu", "maxNSU", "maxNsu"), ult_nsu)

        raw_docs = _get_first(data, "documentos", "docs", "nfes", "data") or []
        if not isinstance(raw_docs, list):
            raw_docs = []

        docs: list[ResumoNFeDestinada] = []
        for item in raw_docs:
            if not isinstance(item, dict):
                continue
            doc = self._parse_documento(item)
            if doc is not None:
                docs.append(doc)

        log.info(
            "sefaz_mde.focus.baixar",
            ult_nsu=ult_nsu,
            max_nsu=max_nsu,
            docs=len(docs),
        )
        return ResultadoDistribuicao(documentos=docs, ult_nsu=ult_nsu, max_nsu=max_nsu)

    @staticmethod
    def _parse_documento(item: dict[str, object]) -> ResumoNFeDestinada | None:
        """Extrai campos de um documento do lote (resNFe ou nfeProc).

        Tolerante a aliases de chave (snake_case / camelCase / variações).
        Retorna None se não houver chave_nfe ou NSU.
        """
        chave = str(
            _get_first(item, "chave_nfe", "chaveNFe", "chave_acesso", "chave") or ""
        ).strip()
        if not chave or len(chave) != 44:
            return None

        nsu_raw = _get_first(item, "nsu", "NSU")
        if nsu_raw is None:
            return None
        nsu = _coerce_int(nsu_raw, -1)
        if nsu < 0:
            return None

        # Tipo: resNFe → resumo, nfeProc → completo
        tipo_raw = str(
            _get_first(item, "tipo", "tipo_documento", "schema", "tipoDocumento") or ""
        ).lower()
        tipo: TipoDocumentoMde = "completo" if "nfeproc" in tipo_raw or "completo" in tipo_raw else "resumo"

        emitente_cnpj = str(
            _get_first(item, "emitente_cnpj", "cnpjEmitente", "cnpj_emitente") or ""
        ) or None
        emitente_nome = str(
            _get_first(item, "emitente_nome", "nomeEmitente", "nome_emitente", "xNome") or ""
        ) or None

        valor_raw = _get_first(item, "valor_total", "valorTotal", "vNF", "valor")
        valor: Decimal | None = None
        if valor_raw is not None:
            try:
                valor = Decimal(str(valor_raw))
            except InvalidOperation:
                valor = None

        dh_raw = _get_first(item, "dh_emissao", "dhEmissao", "data_emissao", "dhEmi")
        dh_emissao: datetime | None = None
        if isinstance(dh_raw, str) and dh_raw:
            try:
                dh_emissao = datetime.fromisoformat(dh_raw.replace("Z", "+00:00"))
            except ValueError:
                dh_emissao = None

        xml_completo: str | None = None
        if tipo == "completo":
            xml_raw = _get_first(item, "xml_completo", "xmlCompleto", "xml", "nfeProc")
            if isinstance(xml_raw, str) and xml_raw:
                xml_completo = xml_raw

        return ResumoNFeDestinada(
            chave_nfe=chave,
            nsu=nsu,
            emitente_cnpj=emitente_cnpj,
            emitente_nome=emitente_nome,
            valor_total=valor,
            dh_emissao=dh_emissao,
            tipo_documento=tipo,
            xml_completo=xml_completo,
        )


class SefazMdeErro(RuntimeError):
    """Erro irrecuperável do DistribuiçãoDFe (4xx/5xx ou resposta inválida)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_sefaz_mde_provider(settings: Settings) -> SefazMdeProvider:
    """Factory: Focus NFe real se ``FOCUS_NFE_TOKEN`` setado; senão Fake.

    Análogo a ``build_billing_provider`` (Marco 2) e ao padrão de providers
    desta codebase. A credencial liga o provider real — zero fake em prod.
    """
    if settings.FOCUS_NFE_TOKEN:
        log.info("sefaz_mde.provider", provider="focus")
        return FocusSefazMdeProvider(settings)
    log.debug("sefaz_mde.provider", provider="fake")
    return _FakeSefazMdeProvider()


# ── helpers ──────────────────────────────────────────────────────────────────


def _get_first(d: dict[str, object], *keys: str) -> object | None:
    """Retorna o primeiro valor não-None/não-vazio para as chaves dadas."""
    for k in keys:
        v = d.get(k)
        if v is not None and v != "":
            return v
    return None


def _coerce_int(value: object, default: int) -> int:
    """Converte valor de JSON tolerante (str/int, com possível zero-padding NSU).

    Retorna ``default`` quando o valor é ausente, booleano ou não-numérico —
    o parser do provider externo é best-effort e não pode quebrar por lixo.
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default
