"""Classificador puro de mensagens e-CAC por palavra-chave (Sprint 6 PR2).

Versão determinística — zero I/O, sem LLM. Suficiente para o MVP detectar
intimações com prazo (encaminhamento marketplace §10) e priorizar.
O classificador LLM completo (intent + extração de prazo via NER) entra no
PR3 ou Sprint 11 conforme §11.1 (cobertura assistente).

A versão é parte do output para reproduzir resultados — se a heurística mudar,
mensagens classificadas antes não são recalculadas (princípio §8.2).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

CLASSIFICADOR_VERSAO = "kw-2026.05.01"


@dataclass(frozen=True, slots=True)
class Classificacao:
    """Resultado do classificador. Inalterável após emitido."""

    tipo: str  # intimacao | aviso | informativa | outro
    prioridade: str  # alta | media | baixa
    prazo_resposta: date | None
    encaminha_marketplace: bool
    versao: str = CLASSIFICADOR_VERSAO


_PALAVRAS_INTIMACAO = (
    "intimacao",
    "intimação",
    "intimar",
    "auto de infracao",
    "auto de infração",
    "termo de inicio de fiscalizacao",
    "termo de início de fiscalização",
    "mpf",  # Mandado de Procedimento Fiscal
    "comparecer",
    "ciencia obrigatoria",
    "ciência obrigatória",
)
_PALAVRAS_AVISO = (
    "aviso",
    "alerta",
    "atencao",
    "atenção",
    "pendencia",
    "pendência",
    "divergencia",
    "divergência",
    "cobranca",
    "cobrança",
    "saldo devedor",
)
_PALAVRAS_PRAZO_CURTO = (
    "30 dias",
    "trinta dias",
    "15 dias",
    "quinze dias",
    "10 dias",
    "dez dias",
)
_REGEX_PRAZO_DIAS = re.compile(
    r"prazo\s+(?:de\s+)?(\d{1,3})\s+dias", re.IGNORECASE
)
_REGEX_DATA_LIMITE = re.compile(
    r"at[eé]\s+(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})", re.IGNORECASE
)


def _normalizar(texto: str) -> str:
    """Lowercase + sem acentos para matching robusto."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acentos.lower()


def classificar(assunto: str, corpo: str | None) -> Classificacao:
    """Classifica uma mensagem e-CAC por palavra-chave.

    Heurística:
      * "intimacao", "auto de infracao", "MPF", "comparecer" → tipo=intimacao,
        prioridade=alta, encaminha_marketplace=True (§9.3 — contencioso fora
        de escopo do produto).
      * "aviso", "pendencia", "divergencia", "cobranca" → tipo=aviso,
        prioridade=media (alta se conter prazo curto).
      * Demais → tipo=informativa, prioridade=baixa.

    Extrai prazo de "prazo de N dias" ou data limite "até DD/MM/AAAA".
    """
    texto_norm = _normalizar(f"{assunto} {corpo or ''}")

    prazo_resposta = _extrair_prazo(corpo or "", texto_norm)

    if any(p in texto_norm for p in _PALAVRAS_INTIMACAO):
        return Classificacao(
            tipo="intimacao",
            prioridade="alta",
            prazo_resposta=prazo_resposta,
            encaminha_marketplace=True,
        )

    if any(p in texto_norm for p in _PALAVRAS_AVISO):
        prio = (
            "alta"
            if any(p in texto_norm for p in _PALAVRAS_PRAZO_CURTO)
            else "media"
        )
        return Classificacao(
            tipo="aviso",
            prioridade=prio,
            prazo_resposta=prazo_resposta,
            encaminha_marketplace=False,
        )

    return Classificacao(
        tipo="informativa",
        prioridade="baixa",
        prazo_resposta=prazo_resposta,
        encaminha_marketplace=False,
    )


def _extrair_prazo(corpo: str, texto_norm: str) -> date | None:
    """Tenta extrair data limite — primeiro "até DD/MM/AAAA", depois "prazo de N dias".

    Quando só há prazo em dias (sem data explícita), calcula data limite a partir
    de ``date.today()``. v2 da heurística (CLASSIFICADOR_VERSAO=kw-2026.05.01).
    """
    m = _REGEX_DATA_LIMITE.search(corpo)
    if m:
        dia, mes, ano = (int(g) for g in m.groups())
        try:
            return date(ano, mes, dia)
        except ValueError:
            return None
    m2 = _REGEX_PRAZO_DIAS.search(corpo)
    if m2:
        try:
            dias = int(m2.group(1))
        except (TypeError, ValueError):
            return None
        if 1 <= dias <= 365:
            return date.today() + timedelta(days=dias)
    return None
