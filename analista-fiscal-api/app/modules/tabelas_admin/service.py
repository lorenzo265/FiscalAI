"""TabelaAdminService — orquestra POST de vigência tributária (Sprint 19.5 PR1).

Fluxo único para os 7 tipos de tabela:

  1. **Validação §8.6** — chama o validador puro do tipo (faixas progressivas,
     plausibilidade, salário mínimo). Falha → 422 ``VigenciaTributariaInvalida``.

  2. **Idempotência §8.9** — computa ``idempotency_key`` = ``uuid5`` se o
     caller não passou. Consulta o log; se hit:
       * payload idêntico ao do log anterior → devolve o log (200 no-op).
       * payload divergente → 409 ``VigenciaTributariaJaPostada``.

  3. **Anti-regressão temporal** — ``valid_from`` precisa ser > max existente.
     Defesa em profundidade — o trigger SCD ainda fecharia valid_to da vigência
     anterior, mas devolver 422 explícito permite ao admin entender que
     postou retroativo por engano. Para seed retroativo legítimo (pendência
     #37 — INSS 2024), o admin precisa rodar via SQL direto, não via API.

  4. **INSERT na tabela SCD** — repo bridge faz add_all. Trigger
     ``scd_close_previous_valid_to`` (migration 0025) fecha ``valid_to``
     da vigência anterior automaticamente.

  5. **INSERT no log de auditoria** — append-only (REVOKE UPDATE/DELETE).

  6. **Commit + log estruturado** — observabilidade §8.10.

A canonicalização do payload para hashing é determinística: ``model_dump(mode='json')``
serializa Decimal → str e date → ISO; depois ``json.dumps(sort_keys=True,
separators=(',', ':'))`` produz string única por payload.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, TypeVar
from uuid import UUID, uuid5

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.alertas_repo import AlertaAdminRepo
from app.modules.tabelas_admin.repo import (
    SCDTabelasRepo,
    VigenciaTabelaLogRepo,
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
from app.modules.tabelas_admin.validadores import (
    validar_vigencia_cbs_ibs,
    validar_vigencia_fgts,
    validar_vigencia_icms_uf,
    validar_vigencia_inss,
    validar_vigencia_irrf,
    validar_vigencia_presuncao_lp,
    validar_vigencia_simples_nacional,
)
from app.shared.db.models import VigenciaTabelaLog
from app.shared.exceptions import (
    VigenciaTributariaInvalida,
    VigenciaTributariaJaPostada,
)
from app.shared.idempotency import NS_TABELA_ADMIN

log = structlog.get_logger(__name__)


_PayloadT = TypeVar("_PayloadT", bound=BaseModel)


def _canonical_json(payload: BaseModel) -> str:
    """Serializa o payload de forma estável e determinística para hashing.

    Pydantic v2 ``mode='json'`` já converte Decimal→str e date→ISO. O
    ``json.dumps`` com ``sort_keys=True`` + ``separators=(',', ':')`` garante
    que mudança de ordem dos campos no JSON do admin não muda a chave.
    """
    snapshot = payload.model_dump(mode="json")
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"))


def computar_idempotency_key(
    *, tipo_tabela: str, valid_from: date, payload: BaseModel
) -> UUID:
    """``uuid5(NS_TABELA_ADMIN, "{tipo}|{valid_from}|sha256(payload_canonical)")``.

    Helper público — testes e PR3 (sugestão→aprovação) também usam.
    """
    canonical = _canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return uuid5(
        NS_TABELA_ADMIN,
        f"{tipo_tabela}|{valid_from.isoformat()}|{digest}",
    )


class TabelaAdminService:
    """Orquestra criação de vigência tributária via painel admin."""

    def __init__(
        self,
        *,
        log_repo: VigenciaTabelaLogRepo,
        scd_repo: SCDTabelasRepo,
        alerta_repo: AlertaAdminRepo | None = None,
    ) -> None:
        self._log_repo = log_repo
        self._scd_repo = scd_repo
        # ``alerta_repo`` é opcional — quando passado (router PR2+), o
        # service marca como resolvidos os alertas relacionados ao tipo+ano
        # antes do commit final. Quando ausente (tests do PR1), comportamento
        # original preservado.
        self._alerta_repo = alerta_repo

    # ── Helper genérico ────────────────────────────────────────────────

    async def _checar_idempotencia_e_max_valid_from(
        self,
        *,
        tipo_tabela: str,
        payload: BaseModel,
        idempotency_key_input: UUID | None,
        max_valid_from_db: date | None,
        valid_from: date,
    ) -> tuple[UUID, VigenciaTabelaLog | None]:
        """Idempotência + anti-regressão temporal.

        Retorna ``(key_efetiva, log_existente_ou_None)``. Se ``log_existente``
        não-None, o caller usa ele direto (no-op idempotente). Se for None,
        o caller prossegue com INSERT.
        """
        key = idempotency_key_input or computar_idempotency_key(
            tipo_tabela=tipo_tabela,
            valid_from=valid_from,
            payload=payload,
        )

        existente = await self._log_repo.por_idempotency_key(key)
        if existente is not None:
            # Re-POST com mesma chave: confere se payload bate. O JSONB persistido
            # foi gravado a partir de ``model_dump(mode='json')`` — comparação
            # determinística sobre o mesmo formato canônico.
            payload_atual = json.loads(_canonical_json(payload))
            if existente.payload_jsonb != payload_atual:
                raise VigenciaTributariaJaPostada(
                    f"idempotency_key {key} já registrada para tipo "
                    f"{existente.tipo_tabela!r} com payload divergente "
                    f"(log_id={existente.id}); gere uma nova chave ou ajuste "
                    f"o payload para bater com o original",
                )
            return key, existente

        # Anti-regressão temporal: valid_from precisa ser > max existente.
        # Seed retroativo legítimo (pendência #37 — INSS 2024) roda via SQL
        # direto, não via API. Esta API é para vigências NOVAS.
        if max_valid_from_db is not None and valid_from <= max_valid_from_db:
            raise VigenciaTributariaInvalida(
                f"valid_from {valid_from} não é posterior à vigência ativa "
                f"({max_valid_from_db}); para seed retroativo, rode via SQL "
                f"direto ou nova migration",
            )

        return key, None

    async def _gravar_log(
        self,
        *,
        session: AsyncSession,
        tipo_tabela: str,
        payload: BaseModel,
        idempotency_key: UUID,
        valid_from: date,
        fonte_norma: str,
        registros_criados: int,
        usuario_admin_id: UUID | None,
    ) -> VigenciaTabelaLog:
        log_row = VigenciaTabelaLog(
            tipo_tabela=tipo_tabela,
            valid_from=valid_from,
            fonte_norma=fonte_norma,
            payload_jsonb=json.loads(_canonical_json(payload)),
            usuario_admin_id=usuario_admin_id,
            idempotency_key=idempotency_key,
            registros_criados=registros_criados,
        )
        await self._log_repo.criar(log_row)
        # Resolução automática de alertas relacionados (Sprint 19.5 PR2):
        # se ``alerta_repo`` foi injetado, marca como resolvidos todos os
        # alertas abertos do mesmo (tipo_tabela, ano) ANTES do commit —
        # nova vigência + auto-resolução na mesma transação.
        alertas_resolvidos = 0
        if self._alerta_repo is not None:
            alertas_resolvidos = (
                await self._alerta_repo.resolver_relacionados(
                    tipo_tabela=tipo_tabela, ano=valid_from.year
                )
            )
        await session.commit()
        log.info(
            "tabelas_admin.vigencia_criada",
            tipo_tabela=tipo_tabela,
            valid_from=valid_from.isoformat(),
            idempotency_key=str(idempotency_key),
            registros_criados=registros_criados,
            alertas_auto_resolvidos=alertas_resolvidos,
        )
        return log_row

    # ── Métodos públicos: 1 por tipo ──────────────────────────────────

    async def criar_vigencia_inss(
        self,
        session: AsyncSession,
        payload: VigenciaInssIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_inss(payload)
        max_db = await self._scd_repo.max_valid_from_inss()
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="inss",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_inss(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="inss",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_irrf(
        self,
        session: AsyncSession,
        payload: VigenciaIrrfIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_irrf(payload)
        max_db = await self._scd_repo.max_valid_from_irrf()
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="irrf",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_irrf(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="irrf",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_fgts(
        self,
        session: AsyncSession,
        payload: VigenciaFgtsIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_fgts(payload)
        max_db = await self._scd_repo.max_valid_from_fgts()
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="fgts",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_fgts(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="fgts",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_simples_nacional(
        self,
        session: AsyncSession,
        payload: VigenciaSimplesNacionalIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_simples_nacional(payload)
        # Anti-regressão é por anexo — outro anexo na mesma data é legítimo.
        max_db = await self._scd_repo.max_valid_from_simples(payload.anexo)
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="simples_nacional",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_simples_nacional(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="simples_nacional",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_presuncao_lp(
        self,
        session: AsyncSession,
        payload: VigenciaPresuncaoLpIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_presuncao_lp(payload)
        max_db = await self._scd_repo.max_valid_from_presuncao()
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="presuncao_lp",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_presuncao_lp(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="presuncao_lp",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_icms_uf(
        self,
        session: AsyncSession,
        payload: VigenciaIcmsUfIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_icms_uf(payload)
        # Anti-regressão precisa ser por UF — postar SP nova sem mexer em MG.
        # Verificamos o MIN dos max por UF presentes no payload — se uma das
        # UFs do payload já tem vigência >= valid_from, abortamos.
        max_por_uf = [
            await self._scd_repo.max_valid_from_icms(a.uf)
            for a in payload.aliquotas
        ]
        max_relevante = max(
            (m for m in max_por_uf if m is not None), default=None
        )
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="icms_uf",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_relevante,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_icms_uf(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="icms_uf",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    async def criar_vigencia_cbs_ibs(
        self,
        session: AsyncSession,
        payload: VigenciaCbsIbsIn,
        *,
        usuario_admin_id: UUID | None = None,
    ) -> VigenciaTabelaLog:
        validar_vigencia_cbs_ibs(payload)
        max_db = await self._scd_repo.max_valid_from_cbs_ibs()
        key, existente = await self._checar_idempotencia_e_max_valid_from(
            tipo_tabela="cbs_ibs",
            payload=payload,
            idempotency_key_input=payload.idempotency_key,
            max_valid_from_db=max_db,
            valid_from=payload.valid_from,
        )
        if existente is not None:
            return existente
        n = await self._scd_repo.inserir_cbs_ibs(
            payload, fonte_norma=payload.fonte_norma
        )
        return await self._gravar_log(
            session=session,
            tipo_tabela="cbs_ibs",
            payload=payload,
            idempotency_key=key,
            valid_from=payload.valid_from,
            fonte_norma=payload.fonte_norma,
            registros_criados=n,
            usuario_admin_id=usuario_admin_id,
        )

    # ── GET historico + snapshot vigente ──────────────────────────────

    async def historico(
        self, tipo_tabela: str, *, limit: int = 50
    ) -> list[VigenciaTabelaLog]:
        return await self._log_repo.listar_historico(tipo_tabela, limit=limit)

    async def snapshot_vigente(
        self, tipo_tabela: str, em: date
    ) -> list[dict[str, Any]]:
        """Despacha para o snapshot do tipo correto. Levantar
        ``TipoTabelaDesconhecido`` fica a cargo do router (mapeia URL → service)."""
        despacho = {
            "inss": self._scd_repo.snapshot_inss,
            "irrf": self._scd_repo.snapshot_irrf,
            "fgts": self._scd_repo.snapshot_fgts,
            "simples_nacional": self._scd_repo.snapshot_simples,
            "presuncao_lp": self._scd_repo.snapshot_presuncao,
            "icms_uf": self._scd_repo.snapshot_icms,
            "cbs_ibs": self._scd_repo.snapshot_cbs_ibs,
        }
        fn = despacho[tipo_tabela]
        return await fn(em)


__all__ = ["TabelaAdminService", "computar_idempotency_key"]
