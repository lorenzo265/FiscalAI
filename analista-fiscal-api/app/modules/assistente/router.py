from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Request

from app.modules.assistente.schemas import PerguntaIn, RespostaOut
from app.modules.assistente.service import responder_pergunta
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.llm.deps import LLMClientDep

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/empresas/{empresa_id}/assistente", tags=["assistente"])


@router.post(
    "/perguntar",
    response_model=RespostaOut,
    status_code=200,
    summary="Faz uma pergunta ao assistente fiscal com citação obrigatória",
)
async def perguntar(
    empresa_id: UUID,
    payload: PerguntaIn,
    request: Request,
    _tenant: TenantDep,
    session: SessionDep,
    llm_client: LLMClientDep,
) -> RespostaOut:
    """Endpoint principal do assistente fiscal.

    O LLM responde com base nos fatos do grafo de memória da empresa.
    Toda resposta com valor monetário, data ou CNPJ é verificada deterministicamente
    antes de ser retornada (§8.5 + §8.6). Perguntas out-of-scope são encaminhadas
    ao marketplace de contadores parceiros.
    """
    settings = request.app.state.settings
    log.info("assistente.pergunta", empresa_id=str(empresa_id), len_pergunta=len(payload.pergunta))
    return await responder_pergunta(
        empresa_id=empresa_id,
        payload=payload,
        session=session,
        llm_client=llm_client,
        settings=settings,
    )
