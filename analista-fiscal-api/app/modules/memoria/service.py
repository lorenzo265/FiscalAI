from __future__ import annotations

from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memoria.embeddings import gerar_embedding
from app.modules.memoria.repo import buscar_similares, criar_node
from app.modules.memoria.schemas import ContextoRAG, MemoriaNodeCreate, MemoriaNodeOut
from app.shared.db.models import MemoriaNode
from app.shared.types import JsonObject


async def adicionar_fato(
    empresa_id: UUID,
    tenant_id: UUID,
    payload: MemoriaNodeCreate,
    session: AsyncSession,
    ollama_url: str,
    http_client: httpx.AsyncClient | None = None,
) -> MemoriaNode:
    """Cria nó de memória com embedding gerado localmente (Ollama)."""
    texto_para_embed = f"{payload.tipo}: {payload.rotulo}"
    if payload.atributos:
        texto_para_embed += " " + " ".join(str(v) for v in payload.atributos.values())

    embedding = await gerar_embedding(texto_para_embed, ollama_url, http_client)

    node = await criar_node(
        session=session,
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        tipo=payload.tipo,
        rotulo=payload.rotulo,
        atributos=payload.atributos,
        fonte_id=payload.fonte_id,
        fonte_tipo=payload.fonte_tipo,
        embedding=embedding,
    )
    await session.commit()
    return node


async def buscar_contexto_rag(
    empresa_id: UUID,
    pergunta: str,
    session: AsyncSession,
    ollama_url: str,
    k: int = 5,
    http_client: httpx.AsyncClient | None = None,
) -> ContextoRAG:
    """Busca os k fatos mais relevantes para a pergunta via cosine similarity."""
    embedding = await gerar_embedding(pergunta, ollama_url, http_client)
    rows = await buscar_similares(session, empresa_id, embedding, k=k)

    nodes = [
        MemoriaNodeOut(
            id=row["id"],
            tipo=row["tipo"],
            rotulo=row["rotulo"],
            atributos=row["atributos"],
            fonte_id=row["fonte_id"],
            fonte_tipo=row["fonte_tipo"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    sim_media = (
        sum(float(row["similarity"]) for row in rows) / len(rows) if rows else 0.0
    )

    return ContextoRAG(
        nodes=nodes,
        similaridade_media=sim_media,
        query_usada=pergunta,
    )


def node_para_out(node: MemoriaNode) -> MemoriaNodeOut:
    return MemoriaNodeOut(
        id=node.id,
        tipo=node.tipo,
        rotulo=node.rotulo,
        atributos=node.atributos,
        fonte_id=node.fonte_id,
        fonte_tipo=node.fonte_tipo,
        created_at=node.created_at,
    )


def contexto_para_fontes(contexto: ContextoRAG) -> list[JsonObject]:
    """Converte ContextoRAG em lista de FonteFato-like dicts para o LLMClient."""
    return [
        {
            "id": str(node.id),
            "tipo": node.tipo,
            "payload": f"{node.rotulo}: {' '.join(str(v) for v in node.atributos.values())}",
        }
        for node in contexto.nodes
    ]
