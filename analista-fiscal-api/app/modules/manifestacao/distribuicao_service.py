"""Service — DistribuiçãoDFe (descoberta de NF-e pelo destinatário) — MD-e PR2.

Orquestra o ciclo de sincronização por NSU:
  1. Lê (ou cria) o cursor de NSU da empresa.
  2. Chama o provider em loop até consumir todos os documentos disponíveis
     ou atingir o cap ``max_paginas``.
  3. Faz upsert idempotente de cada documento em ``nfe_destinada`` (§8.9).
  4. Atualiza o cursor com o novo ``ult_nsu`` / ``max_nsu``.
  5. Commita e retorna o resultado da sincronização.

§8.9 — idempotência: upsert garante que re-sync não duplica documentos.
§8.1 — RLS: a sessão deve ter ``SET LOCAL app.tenant_id`` ativo (garantido
         por ``get_session`` via ``SessionDep`` no router).
§8.2 — append-only: ``nfe_destinada`` recebe INSERTs e UPDATEs de campos
         operacionais (NSU, tipo_documento). Nenhum DELETE.

Transmissão de evento (RecepcaoEvento) é PR3 — não implementada aqui.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.manifestacao.distribuicao_repo import DistribuicaoRepo
from app.modules.manifestacao.schemas import SincronizacaoResultadoOut
from app.shared.integrations.sefaz_mde.provider import SefazMdeProvider

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class DistribuicaoService:
    """Serviço de sincronização do DistribuiçãoDFe.

    O repo é criado a partir da session recebida; testes injetam via ``_repo``.
    """

    async def sincronizar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        cnpj: str,
        provider: SefazMdeProvider,
        *,
        max_paginas: int = 10,
        _repo: DistribuicaoRepo | None = None,
    ) -> SincronizacaoResultadoOut:
        """Sincroniza NF-es destinadas via DistribuiçãoDFe.

        Consome lotes de documentos em ordem crescente de NSU até:
          * ``ult_nsu >= max_nsu`` — sem mais documentos no Ambiente Nacional, OU
          * ``paginas >= max_paginas`` — cap atingido (``truncado=True``).

        Args:
            session: sessão async com RLS ativo (``SET LOCAL app.tenant_id``).
            tenant_id: UUID do tenant (herdado do JWT).
            empresa_id: UUID da empresa cujo CNPJ é consultado.
            cnpj: CNPJ da empresa (14 dígitos) — passado ao provider.
            provider: implementação de ``SefazMdeProvider`` (Fake em dev/CI).
            max_paginas: cap de páginas por chamada (anti-loop infinito).
            _repo: injeção de repo para testes (None = cria ``DistribuicaoRepo``).

        Returns:
            ``SincronizacaoResultadoOut`` com contadores e estado do cursor.
        """
        repo = _repo or DistribuicaoRepo(session)
        agora = datetime.now(_TZ_BR)

        # ── 1. Cursor (cria na primeira vez) ─────────────────────────────────
        cursor = await repo.get_cursor(empresa_id)
        if cursor is None:
            cursor = await repo.create_cursor(tenant_id, empresa_id)
            log.info(
                "distribuicao.cursor.criado",
                empresa_id=str(empresa_id),
            )

        novos = 0
        atualizados = 0
        truncado = False
        paginas = 0

        log.info(
            "distribuicao.sincronizar.inicio",
            empresa_id=str(empresa_id),
            ult_nsu=cursor.ult_nsu,
            max_nsu=cursor.max_nsu,
            max_paginas=max_paginas,
        )

        # ── 2. Loop de paginação ─────────────────────────────────────────────
        while True:
            resultado = await provider.baixar_documentos(cnpj, cursor.ult_nsu)

            # ── 3. Upsert de cada documento ───────────────────────────────────
            for doc in resultado.documentos:
                _, is_new = await repo.upsert_destinada(
                    tenant_id, empresa_id, doc, agora
                )
                if is_new:
                    novos += 1
                else:
                    atualizados += 1

            # ── 4. Avança o cursor ────────────────────────────────────────────
            cursor = await repo.update_cursor(
                cursor,
                ult_nsu=resultado.ult_nsu,
                max_nsu=resultado.max_nsu,
                ultima_sync_em=agora,
            )

            paginas += 1

            if resultado.ult_nsu >= resultado.max_nsu:
                # Todos os documentos disponíveis foram consumidos.
                log.info(
                    "distribuicao.sincronizar.completo",
                    empresa_id=str(empresa_id),
                    ult_nsu=resultado.ult_nsu,
                    max_nsu=resultado.max_nsu,
                    novos=novos,
                    atualizados=atualizados,
                    paginas=paginas,
                )
                break

            if paginas >= max_paginas:
                truncado = True
                log.warning(
                    "distribuicao.sincronizar.truncado",
                    empresa_id=str(empresa_id),
                    paginas=paginas,
                    ult_nsu=resultado.ult_nsu,
                    max_nsu=resultado.max_nsu,
                    pendentes=resultado.max_nsu - resultado.ult_nsu,
                )
                break

        # ── 5. Commit ─────────────────────────────────────────────────────────
        await session.commit()

        log.info(
            "distribuicao.sincronizar.finalizado",
            empresa_id=str(empresa_id),
            novos=novos,
            atualizados=atualizados,
            truncado=truncado,
            ult_nsu=cursor.ult_nsu,
            max_nsu=cursor.max_nsu,
        )

        return SincronizacaoResultadoOut(
            novos=novos,
            atualizados=atualizados,
            ult_nsu=cursor.ult_nsu,
            max_nsu=cursor.max_nsu,
            truncado=truncado,
        )
