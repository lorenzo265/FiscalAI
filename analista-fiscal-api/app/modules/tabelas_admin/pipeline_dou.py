"""Pipeline DOU → LLM → Sugestão (Sprint 19.6 PR3 #41).

Tira o ``_processar_tipo`` do worker ``tabelas_varrer_dou`` do estado de
stub. Função pura-ish (assíncrona, com colaboradores injetados) que
processa **uma** matéria DOU completa:

  1. Baixa o PDF via ``http_client.get(materia.url_pdf)``.
  2. Extrai texto via ``extrair_texto_pdf`` (pdfplumber lazy).
  3. Carrega prompt versionado por tipo (``extrair_tabela_<tipo>_v1.md``).
  4. Chama ``llm_client.chamar`` com prompt + texto do PDF.
  5. Parseia JSON da resposta + extrai citações.
  6. Chama ``SugestaoVigenciaService.persistir_extracao_llm`` (que aplica
     re-check determinístico §8.6).

**Injection de colaboradores** = testabilidade. Testes mockam http_client,
llm_client e service; worker injeta instâncias reais via lifespan.

**Pendência operacional rastreada:** worker em prod precisa de `boto3`
ou diretório local para storage do PDF cru se admin quiser auditoria
posterior. Por ora a sugestão guarda `fonte_dou_url` + `recheck_observacoes`
— informação suficiente pra reproduzir.

Princípios cravados:

  * §8.5 — prompt versionado em `app/shared/llm/prompts/extrair_tabela_*_v1.md`.
  * §8.6 — re-check chamado dentro de `persistir_extracao_llm`.
  * §8.8 — pipeline gera **sugestão**, nunca vigência; admin aprova.
  * §8.10 — log estruturado em cada estágio (download/extracao/llm/persist).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Protocol

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.recheck_llm import CitacaoLLM
from app.modules.tabelas_admin.sugestoes_service import (
    SugestaoVigenciaService,
)
from app.shared.db.models import SugestaoVigenciaTabela
from app.shared.integrations.dou.client import MateriaDou
from app.shared.llm.client import LLMRequest

log = structlog.get_logger(__name__)


_PROMPT_POR_TIPO: dict[str, str] = {
    "inss": "extrair_tabela_inss_v1",
    "irrf": "extrair_tabela_irrf_v1",
    "simples_nacional": "extrair_tabela_cgsn_v1",
}


class _LLMCallable(Protocol):
    """Subset de :class:`LLMClient` — facilita mock em testes."""

    async def chamar(self, request: LLMRequest) -> object: ...


class _PdfExtractor(Protocol):
    """Subset de ``extrair_texto_pdf`` — função puro/mockável."""

    def __call__(self, pdf_bytes: bytes) -> object: ...


async def processar_materia_dou(
    session: AsyncSession,
    materia: MateriaDou,
    *,
    tipo_tabela: str,
    http_client: httpx.AsyncClient,
    llm_client: _LLMCallable,
    pdf_extractor: _PdfExtractor,
    service: SugestaoVigenciaService,
    llm_modelo: str = "gemini-2.5-flash",
) -> SugestaoVigenciaTabela | None:
    """Processa **uma** matéria DOU. Retorna sugestão criada ou None se
    skipada (sem PDF, sem prompt, erro de download/parse).

    Não levanta — fail-soft. Caller (worker) itera e ignora None.
    """
    if not materia.url_pdf:
        log.info(
            "tabelas.dou.materia_sem_pdf",
            url=materia.url_html,
            tipo_tabela=tipo_tabela,
        )
        return None

    prompt_nome = _PROMPT_POR_TIPO.get(tipo_tabela)
    if prompt_nome is None:
        log.warning(
            "tabelas.dou.prompt_ausente",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None

    # 1) Download do PDF.
    try:
        resp_pdf = await http_client.get(materia.url_pdf, timeout=30.0)
        resp_pdf.raise_for_status()
        pdf_bytes = resp_pdf.content
    except Exception:
        log.exception(
            "tabelas.dou.download_pdf_falhou",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None

    # 2) Extração de texto via pdfplumber (lazy).
    try:
        extracao = pdf_extractor(pdf_bytes)
        texto_pdf: str = getattr(extracao, "texto_total", "") or ""
    except Exception:
        log.exception(
            "tabelas.dou.extracao_pdf_falhou",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None
    if not texto_pdf.strip():
        log.info(
            "tabelas.dou.pdf_vazio",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None

    # 3) Carrega prompt versionado.
    from app.shared.llm.prompts import get_prompt  # import local — evita ciclos
    try:
        prompt_versionado = get_prompt(prompt_nome)
    except FileNotFoundError:
        log.warning(
            "tabelas.dou.prompt_nao_encontrado",
            tipo_tabela=tipo_tabela,
            prompt=prompt_nome,
        )
        return None

    # 4) Chama LLM.
    prompt_final = prompt_versionado.texto.replace(
        "(O caller injeta o texto extraído do PDF aqui via `.format(texto_pdf=...)`)",
        texto_pdf,
    ).replace(
        "(O caller injeta `.format(texto_pdf=...)`)",
        texto_pdf,
    )
    try:
        resp = await llm_client.chamar(
            LLMRequest(prompt=prompt_final, temperature=0.0)
        )
        resposta_texto: str = getattr(resp, "texto", "")
    except Exception:
        log.exception(
            "tabelas.dou.llm_falhou",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None

    # 5) Parse JSON da resposta.
    payload_llm = _parsear_resposta_llm(resposta_texto)
    if payload_llm is None:
        log.warning(
            "tabelas.dou.llm_resposta_invalida",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None

    confianca_llm = _parse_decimal_field(payload_llm.pop("llm_confianca", "0.5"))
    citacoes_raw = payload_llm.pop("citacoes", [])
    citacoes_llm = _parse_citacoes(citacoes_raw)

    # Preenche fonte_norma a partir da matéria DOU (LLM pode não ter).
    fonte_norma = (
        str(payload_llm.get("fonte_norma"))
        if payload_llm.get("fonte_norma")
        else (
            f"{materia.titulo} — DOU {materia.data_publicacao.isoformat()}"
            + (f" ({materia.secao})" if materia.secao else "")
        )
    )
    payload_llm["fonte_norma"] = fonte_norma

    # 6) Persistir via service (faz re-check + idempotência).
    try:
        sugestao = await service.persistir_extracao_llm(
            session,
            tipo_tabela=tipo_tabela,
            payload_llm=payload_llm,
            citacoes_llm=citacoes_llm,
            confianca_llm=confianca_llm,
            texto_pdf=texto_pdf,
            fonte_dou_url=materia.url_pdf,
            fonte_dou_pagina=None,
            fonte_norma=fonte_norma,
            llm_modelo=llm_modelo,
            llm_versao_prompt=prompt_nome,
        )
        return sugestao
    except Exception:
        log.exception(
            "tabelas.dou.persistir_falhou",
            tipo_tabela=tipo_tabela,
            url=materia.url_pdf,
        )
        return None


def _parsear_resposta_llm(texto: str) -> dict[str, object] | None:
    """Aceita JSON puro ou code fence ```json ... ```. None se inválido."""
    if not texto:
        return None
    s = texto.strip()
    # Remove code fences ```json ... ```
    if s.startswith("```"):
        partes = s.split("```")
        # ``` json\n{...}\n``` → indice 1 tem "json\n{...}\n"
        if len(partes) >= 2:
            corpo = partes[1].lstrip()
            if corpo.lower().startswith("json"):
                corpo = corpo[4:].lstrip()
            s = corpo
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_decimal_field(raw: object) -> Decimal:
    """Coerção defensiva — vazio/inválido cai em 0.5 (média)."""
    try:
        if isinstance(raw, str | int | float):
            return Decimal(str(raw))
    except Exception:  # nosec B110 — coerção defensiva; inválido cai em default 0.5
        pass
    return Decimal("0.5")


def _parse_citacoes(raw: object) -> list[CitacaoLLM]:
    """Aceita lista de dicts ``{pagina, trecho}``; outros formatos → []."""
    if not isinstance(raw, list):
        return []
    out: list[CitacaoLLM] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        trecho = item.get("trecho")
        if not isinstance(trecho, str):
            continue
        pagina_raw = item.get("pagina", 1)
        try:
            pagina = int(pagina_raw) if pagina_raw is not None else 1
        except (TypeError, ValueError):
            pagina = 1
        out.append(CitacaoLLM(pagina=pagina, trecho=trecho))
    return out


__all__ = [
    "processar_materia_dou",
]
