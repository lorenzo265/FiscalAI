"""Aliases de tipos compartilhados do backend (Fase 2 PR4).

Concentra os pontos onde precisamos de ``Any`` legitimamente — sempre dá nome
ao tipo para que o contrato fique explícito no código e seja fácil de auditar.

* :data:`JsonObject` — um objeto JSON arbitrário (raiz é ``dict``). Usado em
  colunas JSONB do Postgres e em payloads de integração externa onde a
  estrutura completa não cabe em ``TypedDict``.
* :data:`JsonValue` — qualquer valor JSON (escalar, lista ou objeto).

Princípio §8 (tipos em contratos públicos): preferimos ``TypedDict`` ou
Pydantic ``BaseModel`` quando a estrutura é conhecida. Estes aliases
são para os casos legítimos de "JSON cru".
"""

from __future__ import annotations

from typing import Any

JsonObject = dict[str, Any]
JsonValue = Any
