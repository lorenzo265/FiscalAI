"""Dependency injection do object storage (Marco 4 #10).

``app.state.storage`` é construído uma vez no lifespan de ``app/main.py``
(reuso do mesmo adapter/cliente boto3 por todo o processo). Este módulo
expõe esse singleton para os routers via FastAPI ``Depends`` — espelhando
o padrão ``SessionDep``/``TenantDep`` de ``app/shared/db/deps.py``.

Routers que geram blob (SPED, notas, pessoal) recebem ``StorageDep`` e
delegam a persistência ao módulo de storage do domínio.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.shared.storage.backend import ObjectStorage


def get_storage(request: Request) -> ObjectStorage:
    """Devolve o ``ObjectStorage`` singleton montado no lifespan."""
    storage: ObjectStorage = request.app.state.storage
    return storage


StorageDep = Annotated[ObjectStorage, Depends(get_storage)]
