"""Service EFD-Reinf (Sprint 11 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.reinf.calcula_retencao import (
    RegimeTomador,
    calcular_retencao_pj_pj,
)
from app.modules.reinf.esocial_payload import (
    BeneficiarioPjInput,
    ContratanteInput,
    RetencaoR4020Input,
    gerar_r4020,
)
from app.modules.reinf.repo import EfdReinfRepo
from app.modules.reinf.schemas import RegistrarRetencaoIn
from app.shared.db.models import EfdReinfEvento
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    EventoReinfJaExiste,
)

log = structlog.get_logger(__name__)


class ReinfService:
    async def registrar_retencao_r4020(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: RegistrarRetencaoIn,
    ) -> EfdReinfEvento:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        periodo = date(payload.competencia.year, payload.competencia.month, 1)

        if await EfdReinfRepo(session).buscar(
            empresa_id, "R-4020", payload.referencia_id
        ):
            raise EventoReinfJaExiste(
                f"Evento R-4020 com referencia {payload.referencia_id} já existe"
            )

        # Calcula retenção conforme regime do TOMADOR (empresa atual).
        resultado = calcular_retencao_pj_pj(
            valor_servico=payload.valor_servico,
            regime_tomador=RegimeTomador(empresa.regime_tributario),
        )

        # Monta payload R-4020 mesmo se SN dispensou retenção — auditoria útil.
        contratante = ContratanteInput(
            cnpj=empresa.cnpj, razao_social=empresa.razao_social
        )
        beneficiario = BeneficiarioPjInput(
            cnpj=payload.cnpj_prestador,
            razao_social=payload.razao_social_prestador,
        )
        retencao_in = RetencaoR4020Input(
            competencia=periodo,
            valor_bruto_servico=payload.valor_servico,
            ir_retido=resultado.ir_retido,
            pis_retido=resultado.pis_retido,
            cofins_retido=resultado.cofins_retido,
            csll_retido=resultado.csll_retido,
            descricao=payload.descricao_servico,
        )
        payload_dict = gerar_r4020(contratante, beneficiario, retencao_in)
        # Anexa o snapshot do algoritmo de retenção (auditoria SCD-friendly).
        payload_dict["_retencao_snapshot"] = {
            "regime_tomador": resultado.regime_tomador.value,
            "sujeito_a_retencao": resultado.sujeito_a_retencao,
            "csrf_total_calculado": str(resultado.csrf_total),
            "csrf_dispensado": resultado.csrf_dispensado,
            "valor_liquido_pago": str(resultado.valor_liquido_pago),
            "algoritmo_versao": resultado.algoritmo_versao,
        }

        evento = EfdReinfEvento(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo_evento="R-4020",
            referencia_tipo="pagamento_servico_pj",
            referencia_id=payload.referencia_id,
            periodo_apuracao=periodo,
            valor_bruto_servico=resultado.valor_servico,
            ir_retido=resultado.ir_retido,
            pis_retido=resultado.pis_retido,
            cofins_retido=resultado.cofins_retido,
            csll_retido=resultado.csll_retido,
            payload=payload_dict,
            status="preparado",
            algoritmo_versao=resultado.algoritmo_versao,
        )
        try:
            await EfdReinfRepo(session).criar(evento)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise EventoReinfJaExiste(
                f"R-4020 com referencia {payload.referencia_id} já existe"
            ) from exc
        await session.refresh(evento)

        log.info(
            "reinf.r4020.criado",
            empresa_id=str(empresa_id),
            referencia_id=str(payload.referencia_id),
            periodo=periodo.isoformat(),
            valor_servico=str(payload.valor_servico),
            ir=str(resultado.ir_retido),
            csrf=str(resultado.pis_retido + resultado.cofins_retido + resultado.csll_retido),
            csrf_dispensado=resultado.csrf_dispensado,
            sujeito=resultado.sujeito_a_retencao,
        )
        return evento


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    return o
