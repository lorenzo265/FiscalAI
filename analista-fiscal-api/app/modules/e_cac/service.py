"""Service de sincronização e classificação de mensagens e-CAC."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol

from app.shared.types import JsonObject
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.e_cac.classificador import classificar
from app.modules.e_cac.repo import MensagensECacRepo
from app.modules.e_cac.schemas import SyncResultadoOut
from app.modules.empresa.repo import EmpresaRepo
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    SerproErro,
    SerproTimeout,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class _ClienteECac(Protocol):
    async def listar_caixa_postal_e_cac(
        self,
        *,
        cnpj: str,
        idempotency_key: str,
        somente_nao_lidas: bool = True,
    ) -> JsonObject: ...


class ECacService:
    async def sincronizar(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        *,
        serpro_client: _ClienteECac | None,
        somente_nao_lidas: bool = True,
    ) -> SyncResultadoOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if serpro_client is None:
            return SyncResultadoOut(
                novas=0,
                classificadas=0,
                total_no_lote=0,
                aviso="SerproClient não inicializado em runtime",
            )

        idempotency_key = _gerar_idempotency_key(empresa_id, date.today())
        try:
            resposta = await serpro_client.listar_caixa_postal_e_cac(
                cnpj=empresa.cnpj,
                idempotency_key=idempotency_key,
                somente_nao_lidas=somente_nao_lidas,
            )
        except (SerproErro, SerproTimeout) as exc:
            log.warning(
                "e_cac.sync.erro",
                empresa_id=str(empresa_id),
                erro=exc.codigo,
            )
            return SyncResultadoOut(
                novas=0,
                classificadas=0,
                total_no_lote=0,
                aviso=f"SERPRO falhou: {exc.codigo}",
            )

        mensagens_raw = _extrair_lista_mensagens(resposta)
        repo = MensagensECacRepo(session)

        novas = 0
        for raw in mensagens_raw:
            id_ext = str(raw.get("idMensagem") or raw.get("id") or "")
            if not id_ext:
                continue
            assunto = str(raw.get("assunto") or raw.get("titulo") or "(sem assunto)")
            corpo = raw.get("corpo") or raw.get("descricao")
            recebida_em = _parse_data(
                raw.get("dataEnvio") or raw.get("recebidaEm")
            )

            inserida = await repo.upsert_recebida(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                id_externo_serpro=id_ext,
                assunto=assunto,
                corpo=corpo if isinstance(corpo, str) else None,
                recebida_em=recebida_em or datetime.now(_TZ_BR),
            )
            if inserida:
                novas += 1

        # Roda classificador determinístico nas não classificadas.
        nao_classificadas = await repo.nao_classificadas(empresa_id)
        classificadas = 0
        for msg in nao_classificadas:
            resultado = classificar(msg.assunto, msg.corpo)
            await repo.aplicar_classificacao(
                msg.id,
                tipo=resultado.tipo,
                prioridade=resultado.prioridade,
                classificador_versao=resultado.versao,
                prazo_resposta=resultado.prazo_resposta,
                encaminhada_marketplace=resultado.encaminha_marketplace,
            )
            classificadas += 1

        await session.commit()
        log.info(
            "e_cac.sync.ok",
            empresa_id=str(empresa_id),
            novas=novas,
            classificadas=classificadas,
            total_lote=len(mensagens_raw),
        )
        return SyncResultadoOut(
            novas=novas,
            classificadas=classificadas,
            total_no_lote=len(mensagens_raw),
        )


# ── helpers puros ────────────────────────────────────────────────────────────


def _gerar_idempotency_key(empresa_id: uuid.UUID, hoje: date) -> str:
    base = f"ecac:{empresa_id}:{hoje.isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, base))


def _extrair_lista_mensagens(resposta: JsonObject) -> list[JsonObject]:
    """SERPRO devolve `dados` como dict ou string JSON; mensagens em `mensagens`."""
    dados_raw = resposta.get("dados")
    if isinstance(dados_raw, dict):
        dados = dados_raw
    elif isinstance(dados_raw, str):
        try:
            import json

            dados = json.loads(dados_raw)
        except (ValueError, TypeError):
            dados = {}
    else:
        dados = {}

    lista = dados.get("mensagens") or dados.get("listaMensagens") or []
    if not isinstance(lista, list):
        return []
    return [m for m in lista if isinstance(m, dict)]


def _parse_data(valor: object) -> datetime | None:
    if not isinstance(valor, str):
        return None
    # SERPRO costuma enviar ISO8601 ou "DD/MM/AAAA HH:MM"
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        pass
    try:
        return datetime.strptime(valor, "%d/%m/%Y %H:%M").replace(tzinfo=_TZ_BR)
    except ValueError:
        return None
