"""Repositório do grafo de memória — inclui busca vetorial por similaridade de cosseno.

O campo `embedding` é VECTOR(768) no Postgres mas não está no SQLAlchemy ORM (gerenciado
por SQL puro). Toda query vetorial usa `text()` para evitar dependência do pgvector em testes.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import MemoriaEdge, MemoriaNode
from app.shared.types import JsonObject


async def criar_node(
    session: AsyncSession,
    tenant_id: UUID,
    empresa_id: UUID,
    tipo: str,
    rotulo: str,
    atributos: JsonObject,
    fonte_id: UUID | None = None,
    fonte_tipo: str | None = None,
    embedding: list[float] | None = None,
) -> MemoriaNode:
    """Cria um nó de memória e persiste o embedding via SQL raw."""
    node = MemoriaNode(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        tipo=tipo,
        rotulo=rotulo,
        atributos=atributos,
        fonte_id=fonte_id,
        fonte_tipo=fonte_tipo,
    )
    session.add(node)
    await session.flush()  # gera o ID

    if embedding is not None:
        vec_str = "[" + ",".join(str(f) for f in embedding) + "]"
        await session.execute(
            text("UPDATE memoria_node SET embedding = :emb WHERE id = :id"),
            {"emb": vec_str, "id": str(node.id)},
        )

    return node


async def buscar_similares(
    session: AsyncSession,
    empresa_id: UUID,
    embedding: list[float],
    k: int = 5,
    tipo: str | None = None,
) -> list[JsonObject]:
    """Busca os k nós mais similares por cosine similarity.

    Retorna lista de dicts com chaves: id, tipo, rotulo, atributos, similarity.
    """
    vec_str = "[" + ",".join(str(f) for f in embedding) + "]"

    _BASE = """
        SELECT id, tipo, rotulo, atributos, fonte_id, fonte_tipo, created_at,
               1 - (embedding <=> :emb::vector) AS similarity
        FROM memoria_node
        WHERE empresa_id = :empresa_id
          AND embedding IS NOT NULL
    """
    if tipo:
        sql = text(_BASE + " AND tipo = :tipo ORDER BY embedding <=> :emb::vector LIMIT :k")
        params: JsonObject = {"emb": vec_str, "empresa_id": str(empresa_id), "k": k, "tipo": tipo}
    else:
        sql = text(_BASE + " ORDER BY embedding <=> :emb::vector LIMIT :k")
        params = {"emb": vec_str, "empresa_id": str(empresa_id), "k": k}

    result = await session.execute(sql, params)
    return [dict(row._mapping) for row in result]


async def buscar_nodes_empresa(
    session: AsyncSession,
    empresa_id: UUID,
    tipo: str | None = None,
    limit: int = 50,
) -> list[MemoriaNode]:
    stmt = select(MemoriaNode).where(MemoriaNode.empresa_id == empresa_id)
    if tipo:
        stmt = stmt.where(MemoriaNode.tipo == tipo)
    stmt = stmt.order_by(MemoriaNode.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def criar_edge(
    session: AsyncSession,
    tenant_id: UUID,
    empresa_id: UUID,
    origem_id: UUID,
    destino_id: UUID,
    tipo: str,
    atributos: JsonObject | None = None,
) -> MemoriaEdge:
    edge = MemoriaEdge(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        origem_id=origem_id,
        destino_id=destino_id,
        tipo=tipo,
        atributos=atributos or {},
    )
    session.add(edge)
    await session.flush()
    return edge
