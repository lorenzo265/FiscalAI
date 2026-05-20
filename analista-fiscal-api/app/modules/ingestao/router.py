from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, UploadFile

from app.modules.ingestao.schemas import DocumentoFiscalOut, IngestaoResultadoOut
from app.modules.ingestao.service import IngestaoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import (
    DocumentoJaIngerido,
    EmpresaNaoEncontrada,
    XmlInvalido,
)

router = APIRouter(prefix="/v1/empresas", tags=["ingestao"])

_MAX_XML_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/{empresa_id}/ingestao/upload",
    response_model=IngestaoResultadoOut,
    status_code=201,
    summary="Ingerir NF-e / NFC-e via upload de XML",
)
async def upload_xml(
    empresa_id: UUID,
    arquivo: UploadFile,
    ctx: TenantDep,
    session: SessionDep,
) -> IngestaoResultadoOut:
    xml_bytes = await arquivo.read(_MAX_XML_BYTES)
    service = IngestaoService(session)
    try:
        doc = await service.ingerir_upload(ctx.tenant_id, empresa_id, xml_bytes)
    except EmpresaNaoEncontrada as e:
        raise e
    except XmlInvalido as e:
        raise e
    except DocumentoJaIngerido as e:
        raise e
    return IngestaoResultadoOut(
        documento=DocumentoFiscalOut.model_validate(doc),
        mensagem="Documento ingerido com sucesso",
    )


@router.get(
    "/{empresa_id}/documentos",
    response_model=list[DocumentoFiscalOut],
    summary="Listar documentos fiscais da empresa",
)
async def listar_documentos(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: str | None = Query(default=None, description="nfe, nfse, nfce…"),
    direcao: str | None = Query(default=None, description="saida ou entrada"),
    limit: int = Query(default=50, le=200),
) -> list[DocumentoFiscalOut]:
    from app.modules.ingestao.repo import DocumentoFiscalRepo

    repo = DocumentoFiscalRepo(session)
    docs = await repo.listar_empresa(empresa_id, tipo=tipo, direcao=direcao, limit=limit)
    return [DocumentoFiscalOut.model_validate(d) for d in docs]
