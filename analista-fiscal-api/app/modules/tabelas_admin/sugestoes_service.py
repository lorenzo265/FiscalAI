"""SugestaoVigenciaService — pipeline DOU → LLM → re-check → sugestão pendente.

Sprint 19.5 PR3 / Camada 3. Princípio inviolável §8.8: o LLM **nunca**
escreve fato — só gera sugestão; aprovação é ato consciente do admin
(``aprovar`` chama ``TabelaAdminService.criar_vigencia_<tipo>`` da Camada 1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.recheck_llm import (
    CitacaoLLM,
    RecheckResultado,
    rechecar_extracao_llm,
)
from app.modules.tabelas_admin.schemas import (
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
)
from app.modules.tabelas_admin.service import TabelaAdminService
from app.modules.tabelas_admin.sugestoes_repo import (
    SugestaoVigenciaRepo,
    idempotency_key_para_dou,
)
from app.shared.db.models import (
    SugestaoVigenciaTabela,
    VigenciaTabelaLog,
)
from app.shared.exceptions import (
    SugestaoVigenciaForaDeFluxo,
    SugestaoVigenciaNaoEncontrada,
)

log = structlog.get_logger(__name__)


# Mapa tipo → schema Pydantic (reuso para serialização payload -> aprovar)
_SCHEMA_POR_TIPO: dict[str, type[BaseModel]] = {
    "inss": VigenciaInssIn,
    "irrf": VigenciaIrrfIn,
    "fgts": VigenciaFgtsIn,
    "simples_nacional": VigenciaSimplesNacionalIn,
    "presuncao_lp": VigenciaPresuncaoLpIn,
    "icms_uf": VigenciaIcmsUfIn,
    "cbs_ibs": VigenciaCbsIbsIn,
}


class SugestaoVigenciaService:
    """Pipeline da Camada 3.

    Métodos:
      * ``persistir_extracao_llm`` — recebe a saída crua do LLM + texto do
        PDF, roda re-check, persiste como sugestão pendente (idempotente
        por URL+tipo).
      * ``aprovar`` — chama Camada 1 com ``payload_jsonb`` + linka log.
      * ``rejeitar`` — marca rejeitada com motivo.
      * ``listar`` — passthrough do repo.
      * ``expirar_pendentes_antigas`` — limpeza periódica.
    """

    def __init__(
        self,
        *,
        sugestao_repo: SugestaoVigenciaRepo,
        tabela_admin_service: TabelaAdminService | None = None,
    ) -> None:
        self._sugestao_repo = sugestao_repo
        # ``tabela_admin_service`` opcional — só obrigatório para ``aprovar``.
        # Listar/rejeitar funcionam sem ele.
        self._tabela_admin_service = tabela_admin_service

    async def persistir_extracao_llm(
        self,
        session: AsyncSession,
        *,
        tipo_tabela: str,
        payload_llm: dict[str, Any],
        citacoes_llm: list[CitacaoLLM],
        confianca_llm: Decimal,
        texto_pdf: str,
        fonte_dou_url: str,
        fonte_dou_pagina: int | None,
        fonte_norma: str,
        llm_modelo: str,
        llm_versao_prompt: str,
    ) -> SugestaoVigenciaTabela:
        """Persiste 1 sugestão pendente. Idempotente por (tipo, url DOU)."""

        # Idempotência §8.9: 2 runs do worker no mesmo mês detectam a mesma
        # URL — devolvemos a sugestão anterior sem reprocessar.
        key = idempotency_key_para_dou(
            url_dou=fonte_dou_url, tipo_tabela=tipo_tabela
        )
        existente = await self._sugestao_repo.por_idempotency_key(key)
        if existente is not None:
            log.info(
                "tabelas.dou.sugestao_idempotente",
                sugestao_id=str(existente.id),
                tipo_tabela=tipo_tabela,
            )
            return existente

        # Re-check determinístico §8.6 — não levanta; preenche observações.
        recheck = rechecar_extracao_llm(
            tipo_tabela=tipo_tabela,
            payload_llm=payload_llm,
            citacoes_llm=citacoes_llm,
            confianca_llm=confianca_llm,
            texto_pdf=texto_pdf,
        )

        # valid_from sai do próprio payload_llm — se está malformado, o
        # re-check já flagou. Defesa adicional: fallback para hoje.
        valid_from_raw = payload_llm.get("valid_from")
        valid_from = _parse_iso_date(valid_from_raw) or date.today()

        sugestao = SugestaoVigenciaTabela(
            tipo_tabela=tipo_tabela,
            valid_from=valid_from,
            payload_jsonb=payload_llm,
            fonte_norma=fonte_norma,
            fonte_dou_url=fonte_dou_url,
            fonte_dou_pagina=fonte_dou_pagina,
            llm_modelo=llm_modelo,
            llm_versao_prompt=llm_versao_prompt,
            llm_confianca=confianca_llm,
            recheck_passou=recheck.passou,
            recheck_observacoes=recheck.observacoes,
            idempotency_key=key,
        )
        sugestao = await self._sugestao_repo.criar(sugestao)
        await session.commit()
        log.info(
            "tabelas.dou.sugestao_criada",
            sugestao_id=str(sugestao.id),
            tipo_tabela=tipo_tabela,
            recheck_passou=recheck.passou,
            llm_confianca=str(confianca_llm),
        )
        return sugestao

    # ── Endpoints aprovar / rejeitar ──────────────────────────────────

    async def aprovar(
        self,
        session: AsyncSession,
        sugestao_id: UUID,
        *,
        usuario_id: UUID | None = None,
    ) -> SugestaoVigenciaTabela:
        if self._tabela_admin_service is None:
            raise RuntimeError(
                "aprovar requer TabelaAdminService injetado no SugestaoService"
            )

        sugestao = await self._sugestao_repo.por_id(sugestao_id)
        if sugestao is None:
            raise SugestaoVigenciaNaoEncontrada(
                f"Sugestão {sugestao_id} não encontrada"
            )
        if sugestao.status != "pendente":
            raise SugestaoVigenciaForaDeFluxo(
                f"Sugestão {sugestao_id} está em status {sugestao.status!r} — "
                f"só 'pendente' pode ser aprovada"
            )

        # Reconstrói o schema Pydantic do tipo e chama Camada 1.
        schema_cls = _SCHEMA_POR_TIPO[sugestao.tipo_tabela]
        payload_modelo: BaseModel = schema_cls.model_validate(
            sugestao.payload_jsonb
        )
        log_row = await self._dispatch_camada_1(
            session,
            tipo_tabela=sugestao.tipo_tabela,
            payload=payload_modelo,
            usuario_admin_id=usuario_id,
        )

        # marcar_aprovada não comita — o commit da Camada 1 já cobriu.
        # Mas precisamos garantir que a transação esteja aberta novamente
        # para o UPDATE da sugestão. Chamamos flush + commit explícito.
        await self._sugestao_repo.marcar_aprovada(
            sugestao,
            vigencia_tabela_log_id=log_row.id,
            aprovada_por_usuario_id=usuario_id,
        )
        await session.commit()
        log.info(
            "tabelas.dou.sugestao_aprovada",
            sugestao_id=str(sugestao.id),
            log_id=str(log_row.id),
        )
        return sugestao

    async def rejeitar(
        self,
        session: AsyncSession,
        sugestao_id: UUID,
        *,
        motivo: str,
    ) -> SugestaoVigenciaTabela:
        sugestao = await self._sugestao_repo.por_id(sugestao_id)
        if sugestao is None:
            raise SugestaoVigenciaNaoEncontrada(
                f"Sugestão {sugestao_id} não encontrada"
            )
        if sugestao.status != "pendente":
            raise SugestaoVigenciaForaDeFluxo(
                f"Sugestão {sugestao_id} está em status {sugestao.status!r} — "
                f"só 'pendente' pode ser rejeitada"
            )
        await self._sugestao_repo.marcar_rejeitada(sugestao, motivo=motivo)
        await session.commit()
        log.info(
            "tabelas.dou.sugestao_rejeitada",
            sugestao_id=str(sugestao.id),
            motivo=motivo[:100],
        )
        return sugestao

    # ── Listagem + limpeza ─────────────────────────────────────────────

    async def listar(
        self,
        *,
        status: str | None = None,
        tipo_tabela: str | None = None,
        limite: int = 100,
    ) -> list[SugestaoVigenciaTabela]:
        return await self._sugestao_repo.listar(
            status=status,  # type: ignore[arg-type]
            tipo_tabela=tipo_tabela,
            limite=limite,
        )

    async def expirar_pendentes_antigas(
        self, session: AsyncSession, *, max_dias: int = 60
    ) -> int:
        n = await self._sugestao_repo.expirar_pendentes_antigas(
            max_dias=max_dias
        )
        await session.commit()
        if n > 0:
            log.info("tabelas.dou.sugestoes_expiradas", n=n, max_dias=max_dias)
        return n

    # ── Helper privado ─────────────────────────────────────────────────

    async def _dispatch_camada_1(
        self,
        session: AsyncSession,
        *,
        tipo_tabela: str,
        payload: BaseModel,
        usuario_admin_id: UUID | None,
    ) -> VigenciaTabelaLog:
        """Chama o método correto da Camada 1 para criar a vigência.

        Despacho explícito por tipo — mypy reclama de dict[str, Callable]
        com assinaturas heterogêneas (payload varia por método). Cast no
        payload é seguro: o caller já fez ``model_validate`` do schema
        correto antes desta chamada.
        """
        svc = self._tabela_admin_service
        assert svc is not None  # garantido pelo caller
        if tipo_tabela == "inss":
            return await svc.criar_vigencia_inss(
                session,
                cast(VigenciaInssIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "irrf":
            return await svc.criar_vigencia_irrf(
                session,
                cast(VigenciaIrrfIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "fgts":
            return await svc.criar_vigencia_fgts(
                session,
                cast(VigenciaFgtsIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "simples_nacional":
            return await svc.criar_vigencia_simples_nacional(
                session,
                cast(VigenciaSimplesNacionalIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "presuncao_lp":
            return await svc.criar_vigencia_presuncao_lp(
                session,
                cast(VigenciaPresuncaoLpIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "icms_uf":
            return await svc.criar_vigencia_icms_uf(
                session,
                cast(VigenciaIcmsUfIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        if tipo_tabela == "cbs_ibs":
            return await svc.criar_vigencia_cbs_ibs(
                session,
                cast(VigenciaCbsIbsIn, payload),
                usuario_admin_id=usuario_admin_id,
            )
        raise RuntimeError(f"tipo_tabela inesperado: {tipo_tabela!r}")


def _parse_iso_date(raw: object) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


__all__ = ["SugestaoVigenciaService"]
