"""Service ICMS (Sprint 11 PR2)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.icms.calcula_icms import calcular_icms_mensal
from app.modules.icms.repo import AliquotaIcmsRepo, ApuracaoIcmsRepo
from app.modules.icms.schemas import ApurarIcmsMensalIn
from app.shared.db.models import ApuracaoFiscal
from app.shared.exceptions import (
    ApuracaoIcmsJaExiste,
    EmpresaNaoEncontrada,
    EmpresaSemUf,
    UfNaoSuportada,
)

log = structlog.get_logger(__name__)


class IcmsService:
    async def apurar_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarIcmsMensalIn,
    ) -> ApuracaoFiscal:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        if not empresa.uf:
            raise EmpresaSemUf(
                f"Empresa {empresa_id} não tem UF cadastrada — apuração ICMS impossível"
            )

        competencia = date(payload.competencia.year, payload.competencia.month, 1)

        if await ApuracaoIcmsRepo(session).buscar(empresa_id, competencia):
            raise ApuracaoIcmsJaExiste(
                f"ICMS de {competencia.isoformat()} já apurado para a empresa"
            )

        aliquota = await AliquotaIcmsRepo(session).vigente_para_uf(
            empresa.uf, competencia
        )
        if aliquota is None:
            raise UfNaoSuportada(
                f"Alíquota ICMS para UF {empresa.uf!r} ausente em "
                f"{competencia.isoformat()}"
            )
        # FA7-m2: aliquota_fecp agora é usada (antes era descartada com _fecp)
        aliquota_interna, aliquota_fecp = aliquota

        resultado = calcular_icms_mensal(
            competencia=competencia.isoformat(),
            uf=empresa.uf,
            aliquota_interna=aliquota_interna,
            debito=payload.debito,
            credito=payload.credito,
            aliquota_fecp=aliquota_fecp,
            saldo_credor_anterior=payload.saldo_credor_anterior,
            ajustes_devedores=payload.ajustes_devedores,
            ajustes_credores=payload.ajustes_credores,
        )

        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo="icms",
            regime=empresa.regime_tributario,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas={
                "uf": empresa.uf,
                "aliquota_interna": str(aliquota_interna),
                "aliquota_fecp": str(aliquota_fecp),
                "aliquota_efetiva": str(resultado.aliquota_efetiva),
                "fonte": "aliquota_icms_uf SCD",
            },
            algoritmo_versao=resultado.algoritmo_versao,
        )
        try:
            await ApuracaoIcmsRepo(session).criar(apuracao)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ApuracaoIcmsJaExiste(
                f"ICMS ({competencia}) já apurado"
            ) from exc
        await session.refresh(apuracao)

        log.info(
            "icms.apurado",
            empresa_id=str(empresa_id),
            competencia=competencia.isoformat(),
            uf=empresa.uf,
            debito=str(payload.debito),
            credito=str(payload.credito),
            a_recolher=str(resultado.icms_a_recolher),
            credor=str(resultado.saldo_credor_a_transportar),
        )
        return apuracao


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_stringify(x) for x in o]
    return o
