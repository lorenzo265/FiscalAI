"""Prompts LLM versionados (ADR 0012).

Convenções:

- Um arquivo `.md` por prompt: ``<modulo>_<nome>_v<N>.md``.
- Bump explícito: mudança de output ⇒ criar ``_v2.md``, não editar ``_v1``.
- Eval suite fixa a versão (campo ``prompt_version`` no JSONL) e falha em mismatch.
- Caller usa ``get_prompt("nome_sem_extensao")`` — extensão e diretório são implícitos.

Cache de leitura em memória do processo (mtime-keyed) — invalida ao editar o arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class PromptVersionado:
    """Carrega um prompt versionado em arquivo .md.

    ``versao`` é derivada do sufixo ``_vN`` do nome de arquivo. ``texto`` é o
    corpo completo, sem front-matter — o caller pode aplicar substituições
    com ``.format(...)`` se o prompt for um template.
    """

    nome: str
    versao: str
    texto: str
    path: Path


@lru_cache(maxsize=64)
def get_prompt(nome: str) -> PromptVersionado:
    """Carrega prompt por nome (sem extensão).

    Ex.: ``get_prompt("assistente_resposta_v1")`` carrega
    ``app/shared/llm/prompts/assistente_resposta_v1.md``.

    Raises:
        FileNotFoundError: se o arquivo não existe.
    """
    path = _PROMPTS_DIR / f"{nome}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt versionado não encontrado: {path}")

    texto = path.read_text(encoding="utf-8")
    versao = nome.rsplit("_v", 1)[-1] if "_v" in nome else "1"

    return PromptVersionado(nome=nome, versao=versao, texto=texto, path=path)


__all__ = ["PromptVersionado", "get_prompt"]
