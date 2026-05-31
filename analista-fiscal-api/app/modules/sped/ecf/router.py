"""Endpoints REST — SPED ECF (Sprint 16 PR2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.modules.sped.ecd.repo import ArquivoSpedRepo
from app.modules.sped.ecf.schemas import (
    ArquivoSpedOut,
    GerarEcfIn,
)
from app.modules.sped.ecf.service import EcfService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["sped"])


@router.post(
    "/{empresa_id}/sped/ecf",
    response_model=ArquivoSpedOut,
    status_code=201,
    summary="Gera Escrituração Contábil Fiscal (ECF) anual — Lucro Presumido",
    description=(
        "Gera o arquivo SPED ECF do ano-calendário informado. Requer empresa "
        "no regime Lucro Presumido com 4 apurações IRPJ + 4 CSLL trimestrais "
        "já registradas em ``apuracao_fiscal`` (Sprint 11 PR1). Se a ECD do "
        "mesmo ano existir, o bloco C (``C040``) é populado com o hash + "
        "recibo. Idempotente §8.9: 409 ``SpedJaGerado`` quando há ativo e "
        "``forcar=false``.\n\n"
        "**Transmissão é ato consciente do cliente (§8.12)**: o sistema "
        "NUNCA transmite ao Fisco. Cliente baixa o ``.txt`` e envia via "
        "PVA com o certificado A1 próprio.\n\n"
        "**Out-of-scope MVP** (Fase 5): Lucro Real (blocos M/N/L completos), "
        "Lucro Arbitrado (Q), imunes/isentas (T detalhado)."
    ),
)
async def gerar_ecf(
    empresa_id: UUID,
    payload: GerarEcfIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ArquivoSpedOut:
    gerada = await EcfService().gerar(
        session,
        ctx.tenant_id,
        empresa_id,
        ano=payload.ano,
        forcar=payload.forcar,
    )
    return ArquivoSpedOut.model_validate(gerada.arquivo)


@router.get(
    "/{empresa_id}/sped/ecf/{sped_id}/download",
    summary="Baixa o .txt SPED ECF",
    description=(
        "Devolve o conteúdo bruto do arquivo SPED em "
        "``application/octet-stream`` com ``Content-Disposition: attachment``. "
        "Hash SHA-256 no header ``X-Sped-Hash`` — cliente compara antes de "
        "transmitir ao PVA."
    ),
)
async def download_ecf(
    empresa_id: UUID,
    sped_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> Response:
    arquivo = await ArquivoSpedRepo(session).por_id(sped_id)
    if (
        arquivo is None
        or arquivo.empresa_id != empresa_id
        or arquivo.tipo != "ecf"
    ):
        raise HTTPException(status_code=404, detail="Arquivo ECF não encontrado")

    nome = (
        f"sped_ecf_"
        f"{arquivo.periodo_inicio.strftime('%Y%m%d')}-"
        f"{arquivo.periodo_fim.strftime('%Y%m%d')}.txt"
    )
    return Response(
        content=bytes(arquivo.conteudo_bytea),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "X-Sped-Hash": arquivo.hash_arquivo,
            "X-Sped-Algoritmo-Versao": arquivo.algoritmo_versao,
        },
    )
