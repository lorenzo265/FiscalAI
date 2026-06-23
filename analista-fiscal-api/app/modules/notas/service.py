from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.notas.repo import NotasRepo
from app.modules.notas.schemas import EmitirNfseIn, EmitirNfseOut, NfseStatusOut
from app.shared.db.models import Empresa
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    MunicipioIbgeAusente,
)
from app.shared.types import JsonObject

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_AVISO_ISS = (
    "A alíquota de ISS informada não foi validada junto à prefeitura do município "
    "do prestador. Confirme a alíquota vigente antes de emitir em produção "
    "(LC 116/2003 art. 8-A: mínimo 2%; art. 8º, II: máximo 5%)."
)


class _FocusClient(Protocol):
    """Subset do FocusNfeClient usado pelo NotasService — facilita injeção em testes."""

    async def emitir_nfse(
        self, payload: JsonObject, *, idempotency_key: str
    ) -> JsonObject: ...

    async def consultar_nfse(self, ref: str) -> JsonObject: ...

log = structlog.get_logger(__name__)


def _gerar_focus_ref(empresa_id: uuid.UUID, numero_rps: str) -> str:
    """Deriva idempotency_key determinístico via UUID5 (§8.9 — idempotência).

    Duas chamadas com mesmos (empresa_id, numero_rps) geram o mesmo ref,
    tornando a emissão idempotente contra retentativas.
    """
    return str(uuid.uuid5(empresa_id, numero_rps))


def _construir_payload_focus(
    empresa: Empresa,
    payload: EmitirNfseIn,
    numero_rps: str,
) -> JsonObject:
    """Monta o payload JSON para POST /v2/nfse da Focus NFe.

    Lógica pura — sem I/O, testável com golden tests.
    """
    base_calculo = (payload.servico_valor - payload.deducoes).max(Decimal("0"))
    valor_iss = (base_calculo * payload.aliquota_iss / Decimal("100")).quantize(
        Decimal("0.01")
    )

    data: JsonObject = {
        "data_emissao": datetime.now(_TZ_BR).date().isoformat(),
        "natureza_operacao": payload.natureza_operacao,
        "prestador": {
            "cnpj": empresa.cnpj,
            "inscricao_municipal": empresa.im or "",
            "codigo_municipio": empresa.codigo_municipio_ibge or "",
        },
        "tomador": {},
        "servico": {
            "valor_servicos": str(payload.servico_valor),
            "valor_deducoes": str(payload.deducoes),
            "valor_iss": str(valor_iss),
            "aliquota": str(payload.aliquota_iss),
            "base_calculo": str(base_calculo),
            "descricao": payload.servico_descricao,
            "item_lista_servico": payload.servico_codigo,
        },
        "numero_rps": numero_rps,
        "serie_rps": "RPS",
        "tipo_rps": "1",
    }

    if payload.cnpj_tomador:
        data["tomador"]["cnpj"] = payload.cnpj_tomador
    if payload.cpf_tomador:
        data["tomador"]["cpf"] = payload.cpf_tomador
    if payload.razao_social_tomador:
        data["tomador"]["razao_social"] = payload.razao_social_tomador
    if payload.email_tomador:
        data["tomador"]["email"] = payload.email_tomador

    return data


class NotasService:
    async def emitir_nfse(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: EmitirNfseIn,
        *,
        focus_client: _FocusClient,
    ) -> EmitirNfseOut:
        empresa_repo = EmpresaRepo(session)
        empresa = await empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if not empresa.codigo_municipio_ibge:
            raise MunicipioIbgeAusente(
                "Cadastre o código IBGE 7-dígitos do município da empresa antes "
                "de emitir NFS-e. Use PATCH /v1/empresas/{eid}/municipio-ibge."
            )

        # RPS sequencial por empresa (exigência ABNT NBR 15032 / ISS-e municipal).
        # SELECT FOR UPDATE garante alocação atômica sob concorrência.
        numero_int = await empresa_repo.alocar_proximo_numero_rps(empresa_id)
        numero_rps = str(numero_int).zfill(9)
        focus_ref = _gerar_focus_ref(empresa_id, numero_rps)

        focus_payload = _construir_payload_focus(empresa, payload, numero_rps)
        resultado = await focus_client.emitir_nfse(focus_payload, idempotency_key=focus_ref)

        repo = NotasRepo(session)
        doc = await repo.criar_nfse(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            cnpj_emitente=empresa.cnpj,
            focus_ref=focus_ref,
            numero_rps=numero_rps,
            valor_total=payload.servico_valor,
            status=resultado.get("status", "processando"),
        )
        await session.commit()

        log.info(
            "notas.nfse.emitida",
            empresa_id=str(empresa_id),
            focus_ref=focus_ref,
            status=resultado.get("status"),
        )
        # Aviso ISS só enquanto a empresa não validou a alíquota (m5 da auditoria
        # Sprints 4-6). Após validação manual via PATCH /v1/empresas/{eid}, some.
        aviso_iss = None if getattr(empresa, "aliquota_iss_validada", False) else _AVISO_ISS

        return EmitirNfseOut(
            focus_ref=focus_ref,
            status=resultado.get("status", "processando"),
            documento_fiscal_id=doc.id,
            mensagem="NFS-e em processamento. Acompanhe o status pelo número de referência.",
            aviso_iss=aviso_iss,
        )

    async def consultar_status(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        focus_ref: str,
        *,
        focus_client: _FocusClient,
    ) -> NfseStatusOut:
        resultado = await focus_client.consultar_nfse(focus_ref)

        # Atualiza status local se mudou
        repo = NotasRepo(session)
        await repo.atualizar_status_nfse(
            focus_ref=focus_ref,
            status=resultado.get("status", "desconhecido"),
            numero=resultado.get("numero"),
            pdf_storage_key=resultado.get("caminho_danfse"),
        )
        await session.commit()

        return NfseStatusOut(
            focus_ref=focus_ref,
            status=resultado.get("status", "desconhecido"),
            numero=resultado.get("numero"),
            numero_rps=resultado.get("numero_rps"),
            pdf_url=resultado.get("url_danfse"),
            xml_url=resultado.get("url_xml_nfse"),
            mensagem_sefaz=resultado.get("mensagem_sefaz"),
        )
