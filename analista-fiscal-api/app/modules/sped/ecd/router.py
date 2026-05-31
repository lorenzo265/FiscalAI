"""Endpoints REST — SPED ECD (Sprint 16 PR1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.modules.sped.ecd.repo import ArquivoSpedRepo
from app.modules.sped.ecd.schemas import (
    ArquivoSpedOut,
    GerarEcdIn,
)
from app.modules.sped.ecd.service import EcdService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["sped"])


@router.post(
    "/{empresa_id}/sped/ecd",
    response_model=ArquivoSpedOut,
    status_code=201,
    summary="Gera Escrituração Contábil Digital (ECD) anual",
    description=(
        "Gera o arquivo SPED ECD do ano-calendário informado e o persiste "
        "como snapshot imutável em ``arquivo_sped``. Idempotente §8.9: "
        "chamadas repetidas com mesmo ``(empresa, ano)`` devolvem 409 "
        "``SpedJaGerado`` a menos que ``forcar=true`` — nesse caso a "
        "versão anterior é marcada como ``superseded_by``. O conteúdo do "
        "``.txt`` SPED fica em ``arquivo_sped.conteudo_bytea``; use o "
        "endpoint ``GET .../sped/ecd/{id}/download`` para baixar.\n\n"
        "**Transmissão é ato consciente do cliente (§8.12)**: o sistema "
        "NUNCA transmite ao Fisco. Cliente baixa o ``.txt`` e envia via "
        "PVA/ReceitaNet com o certificado A1 próprio."
    ),
)
async def gerar_ecd(
    empresa_id: UUID,
    payload: GerarEcdIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ArquivoSpedOut:
    gerada = await EcdService().gerar(
        session,
        ctx.tenant_id,
        empresa_id,
        ano=payload.ano,
        forcar=payload.forcar,
    )
    return ArquivoSpedOut.model_validate(gerada.arquivo)


@router.get(
    "/{empresa_id}/sped/ecd/{sped_id}/download",
    summary="Baixa o .txt SPED ECD",
    description=(
        "Devolve o conteúdo bruto do arquivo SPED em ``application/octet-stream`` "
        "com ``Content-Disposition: attachment; filename=...``. O hash "
        "SHA-256 acompanha em header ``X-Sped-Hash`` — cliente compara "
        "antes de transmitir ao PVA."
    ),
)
async def download_ecd(
    empresa_id: UUID,
    sped_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> Response:
    arquivo = await ArquivoSpedRepo(session).por_id(sped_id)
    if arquivo is None or arquivo.empresa_id != empresa_id:
        raise HTTPException(status_code=404, detail="Arquivo SPED não encontrado")

    nome = (
        f"sped_{arquivo.tipo}_"
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
