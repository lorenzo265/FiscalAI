from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.shared.llm.client import LLMClient


async def get_llm_client(request: Request) -> LLMClient:
    """FastAPI dependency: retorna o LLMClient singleton inicializado no lifespan."""
    client: LLMClient = request.app.state.llm_client
    return client


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
