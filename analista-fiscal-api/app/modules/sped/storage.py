"""Persistência do ``.txt`` SPED em object storage (Marco 4 #10).

Move o conteúdo do arquivo SPED (ECD/ECF/EFD) da coluna BYTEA
``arquivo_sped.conteudo_bytea`` para o object storage
(``app.state.storage`` — local/memory/s3), preenchendo
``arquivo_sped.storage_key``. Em produção (``STORAGE_BACKEND=s3``) isso
tira blobs de 5-50MB do Postgres; em dev (``local``) grava em ``.storage/``.

Três funções, todas Decimal-free e sem efeito colateral de rede além do
storage:

  * ``chave_storage_sped`` — chave determinística por arquivo (inclui o
    ``id`` para que versões supersededas não colidam no storage).
  * ``mover_blob_sped_para_storage`` — escreve o blob no storage, seta
    ``storage_key`` e zera ``conteudo_bytea``. IDEMPOTENTE: se já há
    ``storage_key`` ou não há conteúdo, é no-op. Por ser idempotente,
    serve tanto para o caminho pós-geração quanto para backfill de linhas
    legadas (mesma função).
  * ``ler_conteudo_sped`` — leitura storage-first com fallback BYTEA (para
    linhas legadas ainda não migradas).

**Ordem de escrita (storage antes do commit):** o blob é escrito no storage
ANTES do ``commit`` que aponta para ele. Se o commit falhar depois, sobra um
blob órfão no storage (inofensivo, GC futuro); se o storage falhar antes, a
linha permanece com ``conteudo_bytea`` intacto (sem perda de dado). Object
store e Postgres não são transacionais entre si - este é o trade-off seguro.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ArquivoSped
from app.shared.storage.backend import ObjectStorage, StorageError

log = structlog.get_logger(__name__)

# SPED é ISO-8859-1 (latin-1) por especificação do layout (Ato COTEPE).
_CONTENT_TYPE = "text/plain; charset=ISO-8859-1"


def chave_storage_sped(arquivo: ArquivoSped) -> str:
    """Chave determinística do ``.txt`` SPED no object storage.

    Pattern: ``tenant/<id>/empresa/<id>/sped/<tipo>/<inicio>_<fim>/<arquivo_id>.txt``.
    Inclui o ``arquivo.id`` para que uma versão supersededa e sua sucessora
    (mesmo tenant/empresa/tipo/período) tenham chaves distintas - snapshots
    imutáveis (§8.2) não se sobrescrevem no storage.
    """
    return (
        f"tenant/{arquivo.tenant_id}/empresa/{arquivo.empresa_id}/"
        f"sped/{arquivo.tipo}/"
        f"{arquivo.periodo_inicio.isoformat()}_{arquivo.periodo_fim.isoformat()}/"
        f"{arquivo.id}.txt"
    )


async def mover_blob_sped_para_storage(
    session: AsyncSession,
    arquivo: ArquivoSped,
    storage: ObjectStorage,
) -> bool:
    """Move o ``.txt`` de ``conteudo_bytea`` para o object storage.

    Idempotente (serve de backfill): se ``storage_key`` já existe ou não há
    ``conteudo_bytea``, retorna ``False`` sem tocar no storage. Caso contrário
    escreve o blob, seta ``storage_key``, zera ``conteudo_bytea``, commita e
    retorna ``True``.

    Faz seu próprio ``commit`` - o caller (router/worker) já commitou a linha
    com o conteúdo via service; este é um segundo commit que apenas troca a
    localização do blob.
    """
    if arquivo.storage_key:
        return False
    if arquivo.conteudo_bytea is None:
        return False

    key = chave_storage_sped(arquivo)
    await storage.put_bytes(
        key, bytes(arquivo.conteudo_bytea), content_type=_CONTENT_TYPE
    )
    arquivo.storage_key = key
    arquivo.conteudo_bytea = None
    await session.commit()
    await session.refresh(arquivo)

    log.info(
        "sped.blob.movido_para_storage",
        arquivo_id=str(arquivo.id),
        tipo=arquivo.tipo,
        storage_key=key,
    )
    return True


async def mover_blob_sped_best_effort(
    session: AsyncSession,
    arquivo: ArquivoSped,
    storage: ObjectStorage,
) -> None:
    """Move o blob mas NUNCA falha a operação chamadora.

    A linha já foi commitada com ``conteudo_bytea`` pelo service; um blip do
    storage (S3 fora do ar) não deve transformar uma geração bem-sucedida em
    erro. Em caso de falha, loga warning, faz rollback das mudanças parciais
    e segue - o ``conteudo_bytea`` permanece e o backfill
    (``mover_blob_sped_para_storage``) recupera numa próxima passada.
    """
    try:
        await mover_blob_sped_para_storage(session, arquivo, storage)
    except Exception:
        log.warning(
            "sped.blob.move_falhou",
            arquivo_id=str(arquivo.id),
            tipo=arquivo.tipo,
            exc_info=True,
        )
        await session.rollback()


async def ler_conteudo_sped(
    arquivo: ArquivoSped, storage: ObjectStorage
) -> bytes:
    """Lê o ``.txt`` SPED: storage-first, fallback BYTEA (linha legada).

    Levanta ``StorageError`` se a linha não tem nem ``storage_key`` nem
    ``conteudo_bytea`` (invariante violado - nunca deve ocorrer).
    """
    if arquivo.storage_key:
        return await storage.get_bytes(arquivo.storage_key)
    if arquivo.conteudo_bytea is not None:
        return bytes(arquivo.conteudo_bytea)
    raise StorageError(
        f"ArquivoSped {arquivo.id} sem conteudo_bytea nem storage_key "
        "(invariante violado)."
    )


__all__ = [
    "chave_storage_sped",
    "ler_conteudo_sped",
    "mover_blob_sped_best_effort",
    "mover_blob_sped_para_storage",
]
